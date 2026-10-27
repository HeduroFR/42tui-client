"""Lazy composition for applications reusing the update mixin."""
def resolve_installation_service(app):
    service=getattr(app,'installation_service',None)
    if service is None:
        from ft_tui.app.bootstrap import build_installation_service
        service=build_installation_service(app.session_factory)
    return service
