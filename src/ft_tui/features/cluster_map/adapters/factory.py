"""Compatibility composition for views mounted by small harness applications."""
def resolve_cluster_service(app):
    service=getattr(app,'cluster_service',None)
    if service is None:
        from ft_tui.app.bootstrap import build_cluster_service
        service=build_cluster_service(getattr(app,'session_factory',None),getattr(app,'_configured_cursus_id',None))
    return service
