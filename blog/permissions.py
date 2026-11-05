from rest_framework.permissions import DjangoModelPermissions


class ClinicModelPermissions(DjangoModelPermissions):
    # DRF's default mapping does not require view permission for GET.
    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
    }
