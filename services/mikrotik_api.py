import librouteros


class MikrotikApiService:
    def __init__(self, session_data):
        self._session = session_data

    def connect(self):
        host = self._session.get('mikrotik_host')
        user = self._session.get('mikrotik_user')
        password = self._session.get('mikrotik_password', '')
        port = int(self._session.get('mikrotik_port', 8728))
        if not host or not user:
            return None
        try:
            return librouteros.connect(host=host, username=user, password=password, port=port)
        except Exception:
            return None

    def close(self, api):
        try:
            api.close()
        except Exception:
            pass

    def fetch_wireguard_interfaces(self, api):
        try:
            return [
                {
                    'name': iface.get('name', ''),
                    'public_key': iface.get('public-key', ''),
                    'listen_port': iface.get('listen-port', ''),
                }
                for iface in api('/interface/wireguard/print')
                if iface.get('disabled', 'false') != 'true'
            ]
        except Exception:
            return []

    def fetch_server_public_key(self, api, interface_name):
        try:
            for iface in api('/interface/wireguard/print'):
                if iface.get('name') == interface_name:
                    return iface.get('public-key')
            return None
        except Exception:
            return None

    def get_peers(self, api):
        try:
            return list(api('/interface/wireguard/peers/print'))
        except Exception:
            return []

    def register_peer(self, api, public_key, client_address, client_name, interface_name, keepalive):
        try:
            tuple(api('/interface/wireguard/peers/add', **{
                'name': client_name,
                'interface': interface_name,
                'public-key': public_key,
                'allowed-address': client_address,
                'persistent-keepalive': str(keepalive),
            }))
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_peer(self, api, peer_id):
        try:
            tuple(api('/interface/wireguard/peers/remove', **{'.id': peer_id}))
            return True, None
        except Exception as e:
            return False, str(e)

    def get_ip_addresses(self, api):
        try:
            return list(api('/ip/address/print'))
        except Exception:
            return []
