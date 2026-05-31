import { Controller } from '@hotwired/stimulus'

export default class extends Controller {
  downloadConfig(event) {
    const clientName = event.params.clientName
    const config = event.params.config
    const blob = new Blob([config], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${clientName}.conf`
    document.body.appendChild(a)
    a.click()
    URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  downloadQR(event) {
    const clientName = event.params.clientName
    const container = document.querySelector('#qr-code-container')
    const svg = container ? container.querySelector('svg') : null
    if (!svg) return

    const svgData = new XMLSerializer().serializeToString(svg)
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    const img = new Image()

    img.onload = function () {
      const pad = 20
      canvas.width = img.width + pad * 2
      canvas.height = img.height + pad * 2
      ctx.fillStyle = 'white'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, pad, pad)
      canvas.toBlob(blob => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${clientName}-qr.png`
        document.body.appendChild(a)
        a.click()
        URL.revokeObjectURL(url)
        document.body.removeChild(a)
      })
    }
    img.src = 'data:image/svg+xml;base64,' + btoa(svgData)
  }
}
