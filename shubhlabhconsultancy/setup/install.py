import click
from shubhlabhconsultancy.services.branding_setup_service import setup_branding


def after_install():
    print("Setting up Shubh Labh Consultancy...")

    setup_branding()

    click.secho("Thank you for installing Shubh Labh Consultancy!", fg="green")


def after_app_install(app_name):
    pass
