class UpdateNestedMixin:

    def update_nested_field(self, klass, instance, validated_data):
        nested_serializer = klass(
            data=validated_data, instance=instance, partial=True)
        nested_serializer.is_valid(raise_exception=True)
        nested_serializer.update(
            nested_serializer.instance, nested_serializer.validated_data)

    def update(self, instance, validated_data):

        for field in validated_data.keys():
            assert not isinstance(validated_data[field], list), (
                'The `.update()` method does not support writable m2m '
                'fields by default.')
            if isinstance(validated_data[field], OrderedDict):
                klass = type(self.fields[field])
                self.update_nested_field(klass, getattr(
                    instance, field), validated_data[field])
            else:
                setattr(instance, field, validated_data[field])
        return instance
