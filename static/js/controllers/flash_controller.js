import { Controller } from '@hotwired/stimulus'

export default class extends Controller {
  static values = {
    autoHide: { type: Boolean, default: true },
    duration: { type: Number, default: 3000 },
  }

  connect() {
    if (this.autoHideValue) {
      this._timeout = setTimeout(() => this.hide(), this.durationValue)
    }
  }

  hide() {
    this.element.style.opacity = '0'
    this.element.style.transition = 'opacity 0.3s'
    setTimeout(() => {
      if (this.element.parentElement) this.element.remove()
    }, 300)
  }

  close(event) {
    event.preventDefault()
    clearTimeout(this._timeout)
    this.hide()
  }

  disconnect() {
    clearTimeout(this._timeout)
  }
}
