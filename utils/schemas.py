from six.moves.urllib import parse as urlparse
from rest_framework.schemas import AutoSchema
from rest_framework import permissions
import yaml
import coreapi
import coreschema
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_yasg.inspectors import SwaggerAutoSchema


def simple2schema(stype,  description):
    if stype == "integer":
        return coreschema.Integer(description=description)
    if stype == "string":
        return coreschema.String(description=description)
    if stype == "array":
        return coreschema.Array(description=description)


def in_path(field):
    return field.location == 'path' and field.name == 'id'


class CustomSchema(AutoSchema):
    def get_link(self, path, method, base_url):

        view = self.view

        endpoint_desc = self.view.__doc__

        # print(path)
        method_name = getattr(view, 'action', method.lower())

        method_docstring = getattr(view, method_name, None).__doc__
        if not method_docstring:
            _method_desc = endpoint_desc
        else:
            _method_desc = ''

        fields = self.get_path_fields(path, method)
        try:
            a = method_docstring.split('---')
        except:
            fields += self.get_serializer_fields(path, method)

        else:

            for i in range(0, len(a)):

                yaml_doc = None
                if method_docstring:
                    try:
                        yaml_doc = yaml.load(
                            a[i], Loader=yaml.loader.FullLoader)
                    except:
                        yaml_doc = None

                # Extract schema information from yaml
                if yaml_doc and type(yaml_doc) != str:
                    method_action = yaml_doc.get('method_action', '')
                    method_path = yaml_doc.get('method_path', '')
                    if (method_action == '' or method == method_action) and (method_path == '' or path == method_path):
                        if not method_action == 'GET':
                            fields = list(filter(in_path, fields))

                        _desc = yaml_doc.get('desc', '')

                        _method_desc = _desc
                        params = yaml_doc.get('input', [])
                        for i in params:
                            _name = i.get('name')
                            _desc = i.get('desc')
                            _required = i.get('required', False)
                            _type = i.get('type', 'string')
                            _location = i.get('location', 'form')
                            _elements = i.get('elements', None)
                            field = coreapi.Field(
                                name=_name,
                                location=_location,
                                required=_required,
                                description=_desc,
                                # type=_type,
                                schema=simple2schema(_type, _desc),
                            )
                            fields.append(field)
                else:
                    _method_desc = a[0]
                    fields += self.get_serializer_fields(path, method)
        fields += self.get_pagination_fields(path, method)
        fields += self.get_filter_fields(path, method)

        manual_fields = self.get_manual_fields(path, method)
        fields = self.update_fields(fields, manual_fields)

        if fields and any([field.location in ('form', 'body') for field in fields]):
            encoding = self.get_encoding(path, method)
        else:
            encoding = None

        if base_url and path.startswith('/'):
            path = path[1:]
        print(fields)
        return coreapi.Link(
            url=urlparse.urljoin(base_url, path),
            action=method.lower(),
            encoding=encoding,
            fields=fields,
            description=_method_desc
        )


class Schema(SwaggerAutoSchema):

    def get_operation(self, operation_keys):
        operation = super().get_operation(operation_keys)
        print(operation_keys)
        return operation


schema_view = get_schema_view(
    openapi.Info(
        title="Snippets API",
        default_version='v1',
        description="Test description",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@snippets.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
