
def register_app_blueprints(app):
    """ Loads all the modules for the website APP """

    from importlib import import_module

    print(" APP BLUE PRINTS ")
    for module_name in (
            'root',
            'user',
            'media',
            'landing',
    ):
        module = import_module('app.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        print(" Registering API " + str(module_name))
