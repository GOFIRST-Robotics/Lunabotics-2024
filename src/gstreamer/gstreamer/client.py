from .client_widget import ClientWidget
from rqt_gui_py.plugin import Plugin


class ClientPlugin(Plugin):
    def __init__(self, context):
        super(ClientPlugin, self).__init__(context)
        self.setObjectName("ClientPlugin")
        assert hasattr(context, 'node'), 'Context does not have a node.'
        self._widget = ClientWidget(context.node)
        if context.serial_number() > 1:
            self._widget.setWindowTitle(
                self._widget.windowTitle() + (' (%d)' % context.serial_number()))
        context.add_widget(self._widget)
        