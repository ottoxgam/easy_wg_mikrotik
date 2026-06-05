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
            return librouteros.connect(
                host=host,
                username=user,
                password=password,
                port=port
            )
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
            peers = []
            for p in api('/interface/wireguard/peers/print'):
                p = dict(p)
                self._unpack_meta(p)
                peers.append(p)
            return peers
        except Exception:
            return []

    def register_peer(self, api, public_key, client_address, client_name,
                      interface_name, keepalive, extra=None):

        # ONLY actual RouterOS settings
        ROUTEROS_PEER_PARAMS = {
            'comment',
            'endpoint-address',
            'endpoint-port',
            'preshared-key',
            'disabled',
        }

        params = {
            'name': client_name,
            'interface': interface_name,
            'public-key': public_key,
            'allowed-address': client_address,
        }

        if keepalive:
            params['persistent-keepalive'] = str(keepalive)

        if extra:
            # 1. Filter only the fields allowed by RouterOS
            for k, v in extra.items():
                if k in ROUTEROS_PEER_PARAMS and v:
                    params[k] = v

            # 2. All custom fields → in the comment
            META_KEYS = [
                'private-key',
                'client-address',
                'client-endpoint',
                'client-listen-port',
                'client-allowed-address',
                'client-keepalive',
                'client-dns',
            ]

            meta_parts = []
            for k in META_KEYS:
                v = extra.get(k, '')
                if v:
                    meta_parts.append(f"{k}={v}")

            if meta_parts:
                meta_str = "|".join(meta_parts)
                existing_comment = params.get('comment', '')

                if existing_comment:
                    params['comment'] = f"{existing_comment}||{meta_str}"
                else:
                    params['comment'] = f"||{meta_str}"

        try:
            tuple(api('/interface/wireguard/peers/add', **params))
            return True, None
        except Exception as e:
            return False, str(e)

    def delete_peer(self, api, peer_id):
        try:
            tuple(api('/interface/wireguard/peers/remove', **{'.id': peer_id}))
            return True, None
        except Exception as e:
            return False, str(e)

    def get_peer(self, api, peer_id):
        try:
            peer = next(
                (p for p in api('/interface/wireguard/peers/print')
                 if p.get('.id') == peer_id),
                None
            )
            if peer:
                peer = dict(peer)
                self._unpack_meta(peer)
            return peer
        except Exception:
            return None

    def update_peer(self, api, peer_id, fields):
        try:
            tuple(api('/interface/wireguard/peers/set', **{
                '.id': peer_id,
                **fields
            }))
            return True, None
        except Exception as e:
            return False, str(e)

    def get_ip_addresses(self, api):
        try:
            return list(api('/ip/address/print'))
        except Exception:
            return []

    @staticmethod
    def _unpack_meta(peer):
        """
        Parses custom fields from the comment back into a dictionary.
        Format:
        comment = "text||key=value|key=value"
        """
        comment = peer.get('comment', '')

        if '||' not in comment:
            return

        user_comment, _, meta_str = comment.partition('||')
        peer['comment'] = user_comment

        for part in meta_str.split('|'):
            if '=' in part:
                k, _, v = part.partition('=')
                peer[k.strip()] = v.strip()