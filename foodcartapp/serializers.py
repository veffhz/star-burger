from rest_framework.serializers import ModelSerializer

from foodcartapp.models import Order, Item


class ItemSerializer(ModelSerializer):
    class Meta:
        model = Item
        read_only_fields = ('cost',)
        fields = [
            'quantity',
            'product',
            'cost'
        ]


class OrderSerializer(ModelSerializer):
    products = ItemSerializer(many=True, allow_empty=False, source='items')

    class Meta:
        model = Order
        read_only_fields = ('id',)
        fields = [
            'id',
            'address',
            'firstname',
            'lastname',
            'phonenumber',
            'products'
        ]

    def create(self, validated_data):
        items = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item in items:
            Item.objects.create(order=order, **item)
        return order
