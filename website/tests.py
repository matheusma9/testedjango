from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from website.models import Cliente, Endereco, Carrinho, Categoria, Produto, ItemCarrinho, Venda, Oferta
from django.contrib.auth.models import User
from decimal import Decimal
from rest_framework_jwt.settings import api_settings
from decimal import Decimal
# Create your tests here.


class AccountTests(APITestCase):

    def setUp(self):
        endereco = Endereco.objects.create(
            bairro='Leblon', rua='Rua dos Bobos', numero_casa='0', cep='12345-678', cidade='Rio de Janeiro', uf='RJ')
        user = User.objects.create_user(
            username='turing', password='senhama9', email='alan_turing@lfc.com')
        Cliente.objects.create(user=user, nome='Alan', sobrenome='Turing', cpf=454543, rg=777444, data_nascimento='1912-06-23',
                               sexo='M', endereco=endereco)

    def test_create_account(self):
        """
        Ensure we can create a new account object.
        """
        url = reverse('cliente-list')
        endereco = {
            'bairro': 'a',
            'rua': 'a',
            'numero_casa': 'wre',
            'complemento': 'qewqq',
            'cep': '42346-234',
            'cidade': 'Salvador',
            'uf': 'BA'
        }
        user = {'username': 'usertest',
                'email': 'usertest@test.com',
                'password': 'senha123'}
        data = {'nome': 'Teste',
                'sobrenome': 'Teste',
                'cpf': 5514916,
                'rg': 849898,
                'data_nascimento': '23/06/1912',
                'sexo': 'M',
                'user': user,
                'endereco': endereco,
                'foto': None}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Cliente.objects.count(), 2)
        self.assertEqual(Cliente.objects.get(nome='Teste').nome, 'Teste')

    def test_login(self):
        url = reverse('login')
        data = {'username': 'turing', 'password': 'senhama9'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pk_cliente = response.data.get('cliente', None)
        self.assertIsNotNone(pk_cliente)
        cliente = Cliente.objects.get(pk=pk_cliente)
        self.assertEqual(cliente.user.username, data['username'])


class CarrinhoTests(APITestCase):

    def setUp(self):
        endereco = Endereco.objects.create(
            bairro='Leblon', rua='Rua dos Bobos', numero_casa='0', cep='12345-678', cidade='Rio de Janeiro', uf='RJ')
        user = User.objects.create_user(
            username='turing', password='senhama9', email='alan_turing@lfc.com')
        Cliente.objects.create(user=user, nome='Alan', sobrenome='Turing', cpf=454543, rg=777444, data_nascimento='1912-06-23',
                               sexo='M', endereco=endereco)
        c = Categoria.objects.create(nome='Fruta', slug='fruta')
        p = Produto.objects.create(descricao='Banana', valor=Decimal(
            '1.50'), qtd_estoque=20, qtd_limite=9)
        p.categorias.add(c)
        p.save()
        self.client.login(username='turing', password='senhama9')

    def get_produto(self):
        return Produto.objects.get(descricao='Banana')

    def get_cliente(self, quantidade=5):
        produto = self.get_produto()
        cliente = Cliente.objects.get(nome='Alan')
        cliente.carrinho = Carrinho.objects.create()
        cliente.save()
        cliente.carrinho.itens_carrinho.create(produto=produto, carrinho=cliente.carrinho,
                                               valor=produto.valor, quantidade=quantidade)
        cliente.carrinho.save()
        return cliente

    def test_create(self):
        url = reverse('cliente-carrinho')
        response = self.client.get(url, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Carrinho.objects.count(), 1)

    def test_add(self):
        url = reverse('cliente-carrinho')
        produto = self.get_produto()
        cliente = self.get_cliente()
        data = {'produto': produto.pk, 'quantidade': 5}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Carrinho.objects.count(), 1)
        self.assertEqual(ItemCarrinho.objects.count(), 1)
        item = ItemCarrinho.objects.get()
        self.assertEqual(item.produto.pk, produto.pk)
        self.assertEqual(item.carrinho.pk, cliente.carrinho.pk)

    def test_delete(self):
        produto = self.get_produto()
        cliente = self.get_cliente()
        url = reverse('cliente-carrinho')
        data = {'produto': produto.pk}
        response = self.client.delete(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cliente.carrinho.itens_carrinho.count(), 0)

    def test_editar(self):
        produto = self.get_produto()
        cliente = self.get_cliente()
        url = reverse('cliente-carrinho')
        data = {'produto': produto.pk, 'quantidade': 2}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cliente.carrinho.itens_carrinho.get().quantidade, 2)

    def test_incrementar(self):
        produto = self.get_produto()
        cliente = self.get_cliente()
        url = reverse('cliente-carrinho')
        data = {'produto': produto.pk, 'quantidade': 2}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cliente.carrinho.itens_carrinho.get().quantidade, 7)

    def test_incrementar_gte_limite(self):
        produto = self.get_produto()
        produto.qtd_limite = 3
        produto.save()
        cliente = self.get_cliente()
        url = reverse('cliente-carrinho')
        data = {'produto': produto.pk, 'quantidade': 7}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cliente.carrinho.itens_carrinho.get().quantidade, 3)
        self.assertTrue(response.data.get('error', False))
        self.assertEqual(len(response.data.get('messages', [])), 1)

    def test_incrementar_gte_estoque(self):
        produto = self.get_produto()
        produto.qtd_limite = 30
        produto.qtd_estoque = 3
        produto.save()
        cliente = self.get_cliente()
        url = reverse('cliente-carrinho')
        data = {'produto': produto.pk, 'quantidade': 20}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(cliente.carrinho.itens_carrinho.get().quantidade, 3)
        self.assertTrue(response.data.get('error', False))
        self.assertEqual(len(response.data.get('messages', [])), 1)

    def test_comprar(self):
        produto = self.get_produto()
        cliente = self.get_cliente()
        url = reverse('cliente-compra')
        data = {}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Venda.objects.count(), 1)
        v = Venda.objects.get()
        self.assertEqual(v.itens.get().pk, produto.pk)
        self.assertEqual(cliente.carrinho.itens_carrinho.count(), 0)


class OfertaTests(APITestCase):

    def setUp(self):
        Produto.objects.create(descricao='Banana', valor=Decimal(
            '1.50'), qtd_estoque=20, qtd_limite=9)
        User.objects.create_user(
            username='turing', password='senhama9', email='alan_turing@lfc.com')
        User.objects.create_user(
            username='admin', password='senhama9', email='admin@admin.com', is_staff=True)

    def test_cria_oferta_error_403(self):
        self.client.login(username='turing', password='senhama9')
        url = reverse('oferta-list')
        produto = Produto.objects.get()
        data = {
            'valor': '10.00',
            'produto': produto.pk,
            'validade': '2029-11-26T15:40'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Oferta.objects.count(), 0)

    def test_cria_oferta(self):
        self.client.login(username='admin', password='senhama9')
        url = reverse('oferta-list')
        produto = Produto.objects.get()
        data = {
            'valor': '10.00',
            'produto': produto.pk,
            'validade': '2029-11-26T15:40'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Oferta.objects.count(), 1)
        self.assertEqual(Oferta.objects.get().owner.username, 'admin')

    def test_get_oferta_normal_user(self):
        self.client.login(username='turing', password='senhama9')
        url = reverse('oferta-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_oferta_staff_user(self):
        self.client.login(username='admin', password='senhama9')
        url = reverse('oferta-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_oferta_normal_user(self):
        self.client.login(username='turing', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.patch(
            url, data={'valor': '11.00'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_oferta_normal_user(self):
        self.client.login(username='turing', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.delete(
            url, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_oferta_staff_user(self):
        self.client.login(username='admin', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.patch(
            url, data={'valor': '11.00'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Oferta.objects.get().valor, Decimal('11.00'))

    def test_delete_oferta_staff_user(self):
        self.client.login(username='admin', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.delete(
            url, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Oferta.objects.count(), 0)

    def test_patch_oferta_not_owner(self):
        User.objects.create_user(
            username='admin2', password='senhama9', email='admin@admin.com', is_staff=True)
        self.client.login(username='admin2', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.patch(
            url, data={'valor': '11.00'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_oferta_not_owner(self):
        User.objects.create_user(
            username='admin2', password='senhama9', email='admin@admin.com', is_staff=True)
        self.client.login(username='admin2', password='senhama9')
        owner = User.objects.get(username='admin')
        produto = Produto.objects.get()
        oferta = Oferta.objects.create(owner=owner, valor=Decimal(
            "10.00"), validade='2035-11-26T15:40', produto=produto)
        url = reverse('oferta-detail', kwargs={'pk': oferta.pk})
        response = self.client.delete(
            url, data={'valor': '11.00'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
