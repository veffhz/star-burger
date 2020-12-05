from django.db import models
from django.db.models import Sum, Prefetch
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Restaurant(models.Model):
    name = models.CharField('название', max_length=50)
    address = models.CharField('адрес', max_length=100, blank=True)
    contact_phone = models.CharField('контактный телефон', max_length=50, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'ресторан'
        verbose_name_plural = 'рестораны'


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.distinct().filter(menu_items__availability=True)


class ProductCategory(models.Model):
    name = models.CharField('название', max_length=50)

    class Meta:
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('название', max_length=50)
    category = models.ForeignKey(ProductCategory, null=True, blank=True, on_delete=models.SET_NULL,
                                 verbose_name='категория', related_name='products')
    price = models.DecimalField('цена', max_digits=8, decimal_places=2)
    image = models.ImageField('картинка')
    special_status = models.BooleanField('спец.предложение', default=False, db_index=True)
    description = models.TextField('описание', max_length=200, blank=True)

    objects = ProductQuerySet.as_manager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'товар'
        verbose_name_plural = 'товары'


class RestaurantMenuItemQuerySet(models.QuerySet):

    def available(self):
        return self.filter(availability=True)

    def group_by_restaurant(self):
        restaurant_items = dict()

        items = self.available().select_related('restaurant', 'product').all()

        for item in items:
            restaurant_items.setdefault(item.restaurant, set()).add(item.product)
        return restaurant_items


class RestaurantMenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='menu_items')
    availability = models.BooleanField('в продаже', default=True, db_index=True)

    objects = RestaurantMenuItemQuerySet.as_manager()

    def __str__(self):
        return f"{self.restaurant.name} - {self.product.name}"

    class Meta:
        verbose_name = 'пункт меню ресторана'
        verbose_name_plural = 'пункты меню ресторана'
        unique_together = [
            ['restaurant', 'product']
        ]


class OrderQuerySet(models.QuerySet):
    def cost(self):
        return self.annotate(items_cost=Sum('items__cost'))

    def new_orders(self):
        return self.filter(status=OrderStatusChoices.NEW)

    def fetch_with_products(self):
        for order in self:
            order.products_set = {item.product for item in order.items.all()}
        return list(self)

    def prefetch_products(self):
        prefetch = Prefetch(
            'items', queryset=Item.objects.select_related('product').all()
        )
        return self.prefetch_related(prefetch)


class OrderStatusChoices(models.TextChoices):
    NEW = 'new', _('Необработанный')
    PROC = 'processing', _('Обрабатывается')
    COLL = 'collected', _('Собран')
    DONE = 'done', _('Выполнен')


class PaidMethodChoices(models.TextChoices):
    CASH = 'cash', _('Наличностью')
    CARD = 'card', _('Электронно')


class Order(models.Model):
    address = models.CharField('адрес', max_length=100)
    firstname = models.CharField('имя', max_length=50)
    lastname = models.CharField('фамилия', max_length=50)
    phonenumber = models.CharField('мобильный телефон', max_length=50) # noqa

    status = models.CharField(
        'статус',
        max_length=100,
        choices=OrderStatusChoices.choices,
        default=OrderStatusChoices.NEW
    )

    paid_method = models.CharField(
        'способ оплаты',
        max_length=50,
        choices=PaidMethodChoices.choices,
        default=PaidMethodChoices.CASH
    )

    comment = models.TextField('комментарий', blank=True)

    registered_at = models.DateTimeField('дата создания заказа', default=timezone.now)
    called_at = models.DateTimeField('дата звонка', null=True, blank=True)
    delivered_at = models.DateTimeField('дата доставки', null=True, blank=True)

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE,
        related_name='orders', null=True, blank=True
    )

    objects = OrderQuerySet.as_manager()

    def __str__(self):
        return f'{self.firstname} {self.lastname} {self.address}'

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'


class Item(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items', verbose_name='заказ'
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='order_items', verbose_name='товар'
    )

    quantity = models.PositiveIntegerField('количество')
    cost = models.DecimalField('цена', max_digits=8, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.cost = self.quantity * self.product.price # noqa
        super(Item, self).save(*args, **kwargs)

    def __str__(self):
        return f'{self.product} {self.order}'

    class Meta:
        verbose_name = 'элемент заказа'
        verbose_name_plural = 'элементы заказа'
