from api.print_helper import *
from importlib import import_module

def register_app_blueprints(app):
    """ Loads all the modules for the website APP """

    print_b(" APP BLUE PRINTS ")
    for module_name in (
            'root',
            'user',
            'media',
            'landing',
    ):
        module = import_module('app.{}.routes'.format(module_name))
        app.register_blueprint(module.blueprint)

        #print(" Registering API " + str(module_name))
