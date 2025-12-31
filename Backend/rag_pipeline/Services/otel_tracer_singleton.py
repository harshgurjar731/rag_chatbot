
class OtelTracerSingleton(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(OtelTracerSingleton, cls).__new__(cls)
            cls.instance.otel_tracers = {}
            cls.instance.otel_id_to_project_name = {}
        return cls.instance
