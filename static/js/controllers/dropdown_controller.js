import { Controller } from '@hotwired/stimulus'

export default class extends Controller {
  static targets = ['menu']

  toggle() {
    this.menuTarget.classList.contains('hidden') ? this.show() : this.hide()
  }

  show() {
    this.menuTarget.classList.remove('hidden')
    this._outsideClickHandler = this.hideOnClickOutside.bind(this)
    document.addEventListener('click', this._outsideClickHandler)
  }

  hide() {
    this.menuTarget.classList.add('hidden')
    if (this._outsideClickHandler) {
      document.removeEventListener('click', this._outsideClickHandler)
    }
  }

  hideOnClickOutside(event) {
    if (!this.element.contains(event.target)) this.hide()
  }

  disconnect() {
    if (this._outsideClickHandler) {
      document.removeEventListener('click', this._outsideClickHandler)
    }
  }
}
