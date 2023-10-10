class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.actions = ['import_folder', 'import_image', 'cluster', ]

    def init_plugins(self):
        pass

    def parse_file(self, path):
        pass

    def validate_result(self, action, result):
        # liste d'asserts sur un résultat
        pass

    def provide_data(self, action, plugin):
        pass