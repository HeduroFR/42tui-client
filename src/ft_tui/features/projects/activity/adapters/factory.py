"""Lazy composition for activity screens mounted outside the main app."""
def resolve_activity_service(app):
    service=getattr(app,'activity_service',None)
    if service is None:
        from ft_tui.app.bootstrap import build_activity_service
        service=build_activity_service(getattr(app,'session_factory',None),getattr(app,'_configured_cursus_id',None))
    return service
