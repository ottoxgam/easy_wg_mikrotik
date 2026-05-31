import os
import re
import json
import base64
import io
from datetime import datetime
from functools import wraps

import yaml
import qrcode
import qrcode.image.svg
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, make_response
)
from dotenv import load_dotenv
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from services.mikrotik_api import MikrotikApiService

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

AVAILABLE_LOCALES = ['ko', 'en', 'zh', 'ja']
_LOCALES = {}


def _load_locales():
    locales_dir = os.path.join(os.path.dirname(__file__), 'locales')
    for locale in AVAILABLE_LOCALES:
        path = os.path.join(locales_dir, f'{locale}.yml')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                _LOCALES[locale] = data.get(locale, {})


_load_locales()


def _get_locale():
    return session.get('locale', os.environ.get('DEFAULT_LOCALE', 'ko'))


def _t(key, **kwargs):
    locale = _get_locale()
    data = _LOCALES.get(locale, _LOCALES.get('en', {}))
    parts = key.split('.')
    value = data
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
            if value is None:
                return key
        else:
            return key
    if isinstance(value, str):
        for k, v in kwargs.items():
            value = value.replace(f'%{{{k}}}', str(v))
    return value if not isinstance(value, dict) else key


def _logged_in():
    return bool(session.get('mikrotik_host') and session.get('mikrotik_user'))


app.jinja_env.globals.update(
    t=_t,
    get_locale=_get_locale,
    available_locales=AVAILABLE_LOCALES,
    logged_in=_logged_in,
)


def require_login(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not _logged_in():
            flash(_t('flash.login_required'), 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped


START_IP = 2


def _parse_ros_duration(s):
    total = 0
    for val, unit in re.findall(r'(\d+)([wdhms])', s):
        total += int(val) * {'w': 604800, 'd': 86400, 'h': 3600, 'm': 60, 's': 1}[unit]
    return total


def _peer_status(peer):
    handshake = peer.get('last-handshake', '')
    if not handshake:
        return 'waiting'
    try:
        return 'active' if _parse_ros_duration(handshake) < 120 else 'disconnected'
    except Exception:
        return 'disconnected'


def _generate_keypair():
    priv = X25519PrivateKey.generate()
    priv_b64 = base64.b64encode(priv.private_bytes_raw()).decode()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode()
    return priv_b64, pub_b64


def _next_ip(peers, subnet_prefix):
    used = set()
    for peer in peers:
        addr = peer.get('allowed-address', '')
        if addr.startswith(f'{subnet_prefix}.'):
            try:
                last = int(addr.split('/')[0].split('.')[-1])
                used.add(last)
            except (ValueError, IndexError):
                pass
    ip = START_IP
    while ip in used:
        ip += 1
    return f'{subnet_prefix}.{ip}/32'


def _generate_config(priv_key, address, server_pubkey, endpoint, allowed_ips, keepalive, dns=None):
    cfg = f'[Interface]\nPrivateKey = {priv_key}\nAddress = {address}\n'
    if dns:
        cfg += f'DNS = {dns}\n'
    cfg += (
        f'\n[Peer]\n'
        f'PublicKey = {server_pubkey}\n'
        f'Endpoint = {endpoint}\n'
        f'AllowedIPs = {allowed_ips}\n'
        f'PersistentKeepalive = {keepalive}\n'
    )
    return cfg


def _generate_qr(data):
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(data, image_factory=factory, error_correction=qrcode.constants.ERROR_CORRECT_L)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode('utf-8')


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if _logged_in() else url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if _logged_in():
            return redirect(url_for('dashboard'))
        saved = None
        raw = request.cookies.get('remember_mikrotik_login')
        if raw:
            try:
                saved = json.loads(raw)
            except Exception:
                pass
        return render_template('login.html', saved_login=saved)

    host = request.form.get('mikrotik_host', '').strip() or os.environ.get('MIKROTIK_HOST', '192.168.1.1')
    user = request.form.get('mikrotik_user', '').strip()
    password = request.form.get('mikrotik_password', '').strip()
    port = request.form.get('mikrotik_port', '').strip() or os.environ.get('MIKROTIK_PORT', '8728')
    remember = request.form.get('remember_me') == '1'

    if not host or not user or not password:
        flash(_t('flash.required_fields'), 'error')
        return render_template('login.html', saved_login=None)

    try:
        svc = MikrotikApiService({
            'mikrotik_host': host, 'mikrotik_user': user,
            'mikrotik_password': password, 'mikrotik_port': port,
        })
        api = svc.connect()
        if api:
            svc.close(api)
            session.update(
                mikrotik_host=host, mikrotik_user=user,
                mikrotik_password=password, mikrotik_port=port,
            )
            flash(_t('flash.login_success'), 'success')
            resp = make_response(redirect(url_for('dashboard')))
            if remember:
                resp.set_cookie(
                    'remember_mikrotik_login',
                    json.dumps({'host': host, 'user': user, 'port': port}),
                    max_age=30 * 24 * 3600,
                )
            else:
                resp.delete_cookie('remember_mikrotik_login')
            return resp
        flash(_t('flash.login_failed'), 'error')
        return render_template('login.html', saved_login=None)
    except Exception as e:
        flash(_t('flash.connection_failed', error=str(e)), 'error')
        return render_template('login.html', saved_login=None)


@app.route('/logout', methods=['POST'])
def logout():
    for k in ('mikrotik_host', 'mikrotik_user', 'mikrotik_password', 'mikrotik_port'):
        session.pop(k, None)
    flash(_t('flash.logout_success'), 'success')
    return redirect(url_for('login'))


@app.route('/set_locale/<locale>')
def set_locale(locale):
    if locale in AVAILABLE_LOCALES:
        session['locale'] = locale
        flash(_t('flash.language_changed'), 'success')
    return redirect(url_for('dashboard') if _logged_in() else url_for('login'))


@app.route('/dashboard')
@require_login
def dashboard():
    return render_template('dashboard.html',
        mikrotik_host=session.get('mikrotik_host'),
        mikrotik_user=session.get('mikrotik_user'),
        mikrotik_port=session.get('mikrotik_port'),
    )


@app.route('/clients')
@require_login
def clients_index():
    selected = request.args.get('interface')
    peers, interfaces = [], []
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if api:
            interfaces = svc.fetch_wireguard_interfaces(api)
            all_peers = svc.get_peers(api)
            filtered = [p for p in all_peers if p.get('interface') == selected] if selected else all_peers
            peers = [dict(p, _status=_peer_status(p)) for p in filtered]
            svc.close(api)
        else:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
    except Exception:
        flash(_t('flash.peers_list_error'), 'error')
    return render_template('clients_index.html',
        peers=peers, wireguard_interfaces=interfaces, selected_interface=selected)


@app.route('/clients/new')
@require_login
def clients_new():
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
            return redirect(url_for('dashboard'))
        interfaces = svc.fetch_wireguard_interfaces(api)
        addrs = {a.get('interface'): a.get('address', '') for a in svc.get_ip_addresses(api)}
        svc.close(api)
        for iface in interfaces:
            iface['address'] = addrs.get(iface['name'], '')
        if not interfaces:
            flash(_t('flash.no_wireguard_interfaces'), 'error')
            return redirect(url_for('dashboard'))
        return render_template('clients_new.html',
            wireguard_interfaces=interfaces,
            selected_interface=request.args.get('interface'),
            mikrotik_host=os.environ.get('MIKROTIK_HOST', session.get('mikrotik_host', '')),
        )
    except Exception:
        flash(_t('flash.wireguard_interface_error'), 'error')
        return redirect(url_for('dashboard'))


@app.route('/clients', methods=['POST'])
@require_login
def clients_create():
    iface = request.form.get('interface_name', '').strip()
    endpoint = request.form.get('endpoint', '').strip()
    allowed_ips = request.form.get('allowed_ips', '').strip()
    subnet_prefix = '.'.join(request.form.get('subnet_prefix', '').strip().split('.')[:3])
    keepalive = request.form.get('persistent_keepalive', '').strip()
    dns = request.form.get('dns', '').strip() or None
    name_input = request.form.get('client_name', '').strip()
    comment = request.form.get('comment', '').strip()
    client_keepalive = request.form.get('client_keepalive_new', '').strip()
    client_listen_port = request.form.get('client_listen_port_new', '').strip()

    if not iface:
        flash(_t('flash.interface_required'), 'error')
        return redirect(url_for('clients_new'))
    if not all([endpoint, allowed_ips, subnet_prefix]):
        flash(_t('flash.config_fields_required'), 'error')
        return redirect(url_for('clients_new'))

    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
            return redirect(url_for('clients_new'))

        priv_key, pub_key = _generate_keypair()
        server_pubkey = svc.fetch_server_public_key(api, iface)
        if not server_pubkey:
            flash(_t('flash.server_public_key_error'), 'error')
            svc.close(api)
            return redirect(url_for('clients_new'))

        iface_peers = [p for p in svc.get_peers(api) if p.get('interface') == iface]
        client_addr = _next_ip(iface_peers, subnet_prefix)
        client_name = name_input or f'Client-{client_addr.split("/")[0]}'

        extra = {
            'private-key': priv_key,
            'comment': comment,
            'client-address': client_addr,
            'client-endpoint': endpoint,
            'client-allowed-address': allowed_ips,
            'client-keepalive': client_keepalive or keepalive,
            'client-dns': dns or '',
            'client-listen-port': client_listen_port,
        }
        ok, err = svc.register_peer(api, pub_key, client_addr, client_name, iface, keepalive, extra)
        svc.close(api)
        if not ok:
            flash(_t('flash.peer_registration_failed', error=err), 'error')
            return redirect(url_for('clients_new'))

        cfg = _generate_config(priv_key, client_addr, server_pubkey, endpoint, allowed_ips, keepalive, dns)
        qr = _generate_qr(cfg)
        flash(_t('flash.client_created'), 'success')
        return render_template('clients_result.html',
            client_name=client_name,
            client_address=client_addr,
            interface_name=iface,
            endpoint=endpoint,
            client_config=cfg,
            qr_code=qr,
            created_time=datetime.now().strftime('%m/%d %H:%M'),
        )
    except Exception as e:
        flash(_t('flash.client_creation_error', error=str(e)), 'error')
        return redirect(url_for('clients_new'))


@app.route('/clients/delete', methods=['POST'])
@require_login
def clients_delete():
    peer_id = request.form.get('peer_id', '')
    interface = request.form.get('interface', '')
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
        else:
            ok, err = svc.delete_peer(api, peer_id)
            svc.close(api)
            if ok:
                flash(_t('flash.client_deleted'), 'success')
            else:
                flash(_t('flash.client_delete_failed', error=err), 'error')
    except Exception as e:
        flash(_t('flash.client_delete_failed', error=str(e)), 'error')
    if interface:
        return redirect(url_for('clients_index', interface=interface))
    return redirect(url_for('clients_index'))


@app.route('/clients/edit')
@require_login
def clients_edit():
    peer_id = request.args.get('peer_id', '')
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
            return redirect(url_for('clients_index'))
        peer = svc.get_peer(api, peer_id)
        svc.close(api)
        if not peer:
            flash('Peer not found.', 'error')
            return redirect(url_for('clients_index'))
        return render_template('clients_edit.html', peer=peer,
                               back_interface=request.args.get('interface'))
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('clients_index'))


@app.route('/clients/update', methods=['POST'])
@require_login
def clients_update():
    peer_id = request.form.get('peer_id', '')
    interface = request.form.get('interface', '')

    # All clearable fields — send whatever the form provides (empty = clear on router)
    _map = [
        ('name',                  'name'),
        ('comment',               'comment'),
        ('allowed_address',       'allowed-address'),
        ('persistent_keepalive',  'persistent-keepalive'),
        ('endpoint_address',      'endpoint-address'),
        ('endpoint_port',         'endpoint-port'),
        ('client_address',        'client-address'),
        ('client_dns',            'client-dns'),
        ('client_endpoint',       'client-endpoint'),
        ('client_keepalive',      'client-keepalive'),
        ('client_listen_port',    'client-listen-port'),
        ('client_allowed_address','client-allowed-address'),
    ]
    fields = {api_key: request.form.get(form_key, '').strip() for form_key, api_key in _map}

    # Responder is a checkbox — needs sentinel pattern
    if 'responder_sent' in request.form:
        fields['responder'] = 'true' if request.form.get('responder') else 'false'

    # Preshared key only if explicitly entered (blank = don't touch existing key)
    psk = request.form.get('preshared_key', '').strip()
    if psk:
        fields['preshared-key'] = psk

    if not fields.get('name'):
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('clients_edit', peer_id=peer_id, interface=interface))
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
            return redirect(url_for('clients_index'))
        ok, err = svc.update_peer(api, peer_id, fields)
        svc.close(api)
        if ok:
            flash(_t('flash.client_updated'), 'success')
        else:
            flash(_t('flash.client_update_failed', error=err), 'error')
    except Exception as e:
        flash(_t('flash.client_update_failed', error=str(e)), 'error')
    return redirect(url_for('clients_index', interface=interface) if interface else url_for('clients_index'))


@app.route('/clients/config')
@require_login
def clients_config():
    peer_id = request.args.get('peer_id', '')
    back_interface = request.args.get('interface', '')
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            flash(_t('flash.mikrotik_connection_failed'), 'error')
            return redirect(url_for('clients_index'))
        peer = svc.get_peer(api, peer_id)
        if not peer:
            svc.close(api)
            flash('Peer not found.', 'error')
            return redirect(url_for('clients_index'))
        server_pubkey = svc.fetch_server_public_key(api, peer.get('interface', ''))
        svc.close(api)

        priv_key = peer.get('private-key', '')
        if not priv_key:
            flash('Private key not stored for this peer — config cannot be regenerated.', 'error')
            return redirect(url_for('clients_edit', peer_id=peer_id, interface=back_interface))

        client_addr = peer.get('client-address', '') or peer.get('allowed-address', '')
        endpoint   = peer.get('client-endpoint', '')
        dns        = peer.get('client-dns', '') or None
        allowed_ips= peer.get('client-allowed-address', '0.0.0.0/0')
        keepalive  = (peer.get('client-keepalive', '') or peer.get('persistent-keepalive', '')).rstrip('s')

        cfg = _generate_config(priv_key, client_addr, server_pubkey or '', endpoint, allowed_ips, keepalive, dns)
        qr  = _generate_qr(cfg)
        return render_template('clients_config.html',
            peer=peer,
            client_config=cfg,
            qr_code=qr,
            back_interface=back_interface,
        )
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('clients_index'))


@app.route('/clients/fetch_wireguard_address')
@require_login
def fetch_wireguard_address():
    iface_name = request.args.get('interface', '')
    try:
        svc = MikrotikApiService(session)
        api = svc.connect()
        if not api:
            return jsonify({'error': _t('flash.mikrotik_connection_failed')}), 503
        addrs = svc.get_ip_addresses(api)
        peers = svc.get_peers(api)
        svc.close(api)

        iface = next((a for a in addrs if a.get('interface') == iface_name), None)
        bridge = next((a for a in addrs if a.get('interface') == 'bridge1'), None)
        iface_peers = [p for p in peers if p.get('interface') == iface_name]

        if iface:
            return jsonify({
                'network': iface.get('network'),
                'bridge_network': bridge.get('network') if bridge else None,
                'keepalive': _infer_keepalive(iface_peers),
            })
        return jsonify({'error': _t('flash.interface_required')}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _infer_keepalive(peers):
    from collections import Counter
    values = []
    for peer in peers:
        raw = peer.get('persistent-keepalive', '')
        if raw:
            try:
                values.append(int(raw.rstrip('s')))
            except ValueError:
                pass
    return Counter(values).most_common(1)[0][0] if values else None


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug, host='0.0.0.0', port=port)
