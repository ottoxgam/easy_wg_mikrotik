import { Controller } from '@hotwired/stimulus'

export default class extends Controller {
  static targets = ['interfaceSelect', 'interfaceInfo', 'interfacePublicKey', 'interfaceListenPort']
  static values = {
    wireguardInterfaces: Array,
    serverAddress: String,
  }

  connect() {
    if (this.hasInterfaceSelectTarget && this.interfaceSelectTarget.value) {
      this.updateInterfaceInfo()
    }
  }

  updateInterfaceInfo() {
    if (!this.hasInterfaceSelectTarget) return

    const interfaceName = this.interfaceSelectTarget.value
    if (!interfaceName) {
      if (this.hasInterfaceInfoTarget) this.interfaceInfoTarget.classList.add('hidden')
      return
    }

    const selectedInterface = this.wireguardInterfacesValue.find(i => i.name === interfaceName)

    if (selectedInterface && this.hasInterfaceInfoTarget) {
      if (this.hasInterfacePublicKeyTarget) {
        this.interfacePublicKeyTarget.textContent = selectedInterface.public_key || '없음'
      }
      if (this.hasInterfaceListenPortTarget) {
        this.interfaceListenPortTarget.textContent = selectedInterface.listen_port || '설정되지 않음'
      }

      const subnetInput = this.element.querySelector("input[name='subnet_prefix']")
      const allowedIpsInput = this.element.querySelector("input[name='allowed_ips']")
      if (subnetInput) subnetInput.value = ''
      if (allowedIpsInput) allowedIpsInput.value = ''

      fetch(`/clients/fetch_wireguard_address?interface=${encodeURIComponent(interfaceName)}`)
        .then(r => { if (!r.ok) throw new Error('API error'); return r.json() })
        .then(data => {
          if (data.network) {
            if (subnetInput) subnetInput.value = data.network
            if (allowedIpsInput) {
              allowedIpsInput.value = `${data.network}/24`
              if (data.bridge_network) allowedIpsInput.value += `,${data.bridge_network}/24`
            }
          }
          if (data.keepalive != null) {
            const keepaliveInput = this.element.querySelector("input[name='persistent_keepalive']")
            if (keepaliveInput) keepaliveInput.value = data.keepalive
          }
        })
        .catch(() => {})

      const endpointHostInput = this.element.querySelector("input[name='endpoint_host']")
      if (endpointHostInput && this.serverAddressValue) {
        endpointHostInput.value = this.serverAddressValue
      }
      const endpointPortInput = this.element.querySelector("input[name='endpoint_port_client']")
      if (endpointPortInput && selectedInterface.listen_port) {
        endpointPortInput.value = selectedInterface.listen_port
      }

      this.interfaceInfoTarget.classList.remove('hidden')
    } else if (this.hasInterfaceInfoTarget) {
      this.interfaceInfoTarget.classList.add('hidden')
    }
  }
}
