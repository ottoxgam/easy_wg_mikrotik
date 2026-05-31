import { Application } from '@hotwired/stimulus'
import NewClientController from './controllers/new_client_controller.js'
import ClientResultController from './controllers/client_result_controller.js'
import DropdownController from './controllers/dropdown_controller.js'
import FlashController from './controllers/flash_controller.js'

const application = Application.start()
application.register('new-client', NewClientController)
application.register('client-result', ClientResultController)
application.register('dropdown', DropdownController)
application.register('flash', FlashController)
