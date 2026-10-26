from alphax_grc.grc import site

no_cache = 1


def get_context(context):
    site.base(context, with_frameworks=False)
