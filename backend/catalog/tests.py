"""Regression tests for the product photo endpoints.

These cover the upload -> set primary -> delete lifecycle that had no coverage,
which is how three separate 500s shipped: a duplicated ``product`` kwarg, a
duplicated ``is_primary`` kwarg, and an image field missing from the serializer.
"""

import io
import os
import shutil
import tempfile
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from catalog.image_processing import (
    IMAGE_MAX_SIDE,
    THUMBNAIL_MAX_SIDE,
    process_product_image,
)
from catalog.models import Product, ProductImage

UPLOAD_URL = '/api/product-images/'


def build_image(size=(640, 480), color=(180, 40, 40), image_format='PNG'):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format=image_format)
    return buffer.getvalue()


def png_upload(name='foto.png', size=(640, 480), color=(180, 40, 40)):
    return SimpleUploadedFile(name, build_image(size, color), content_type='image/png')


class ProductImageApiTestCase(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix='mayu-test-media-')
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, True)

        self.user = get_user_model().objects.create_superuser(
            username='admin', email='admin@mayu.test', password='x'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(
            name='Tostones picantes con limón TOM 270G',
            cost_usd=Decimal('1.50'),
            price_usd=Decimal('2.50'),
        )

    def upload(self, product=None, image=None, **extra):
        payload = {'product': (product or self.product).pk}
        payload.update(extra)
        if image is not None:
            payload['image'] = image
        return self.client.post(UPLOAD_URL, payload, format='multipart')

    def set_primary(self, image):
        return self.client.post(f'{UPLOAD_URL}{image.pk}/set_primary/')

    def test_upload_stores_a_processed_webp(self):
        response = self.upload(image=png_upload())

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        image = ProductImage.objects.get(pk=body['id'])
        self.assertTrue(image.image.name.endswith('.webp'))
        self.assertTrue(image.thumbnail)
        self.assertEqual((image.width, image.height), (640, 480))
        self.assertTrue(body['url'].endswith('.webp'))
        self.assertTrue(body['thumbnail_url'].endswith('.webp'))
        self.assertGreater(image.size_bytes, 0)
        self.assertTrue(os.path.exists(image.image.path))

    def test_first_image_becomes_primary_and_later_ones_do_not(self):
        first = self.upload(image=png_upload('a.png')).json()
        second = self.upload(image=png_upload('b.png', color=(40, 180, 40))).json()

        self.assertTrue(first['is_primary'])
        self.assertFalse(second['is_primary'])
        self.assertEqual(ProductImage.objects.filter(is_primary=True).count(), 1)
        self.assertEqual(
            ProductImage.objects.get(pk=first['id']).is_primary, True
        )

    def test_image_is_resized_to_the_configured_maximum(self):
        response = self.upload(image=png_upload(size=(2400, 1800)))
        image = ProductImage.objects.get(pk=response.json()['id'])

        self.assertLessEqual(max(image.width, image.height), IMAGE_MAX_SIDE)
        self.assertEqual((image.width, image.height), (1200, 900))

        with Image.open(image.thumbnail.path) as thumb:
            self.assertLessEqual(max(thumb.size), THUMBNAIL_MAX_SIDE)

    def test_set_primary_moves_the_flag(self):
        first = self.upload(image=png_upload('a.png')).json()
        second = self.upload(image=png_upload('b.png', color=(40, 180, 40))).json()

        response = self.set_primary(ProductImage.objects.get(pk=second['id']))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_primary'])
        self.assertEqual(ProductImage.objects.get(pk=first['id']).is_primary, False)
        self.assertEqual(ProductImage.objects.get(pk=second['id']).is_primary, True)
        self.assertEqual(ProductImage.objects.filter(is_primary=True).count(), 1)

    def test_product_exposes_the_primary_thumbnail(self):
        first = self.upload(image=png_upload('a.png')).json()
        second = self.upload(image=png_upload('b.png', color=(40, 180, 40))).json()
        promoted = ProductImage.objects.get(pk=second['id'])
        self.set_primary(promoted)

        response = self.client.get(f'/api/products/{self.product.pk}/')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        # The serializer absolutises the URL, so compare on the stored path.
        self.assertTrue(body['primary_image_url'].endswith(promoted.thumbnail.url))
        self.assertEqual(len(body['images']), 2)
        self.assertNotEqual(body['primary_image_url'], first['thumbnail_url'])

    def test_delete_removes_the_row_and_the_files(self):
        image = ProductImage.objects.get(pk=self.upload(image=png_upload()).json()['id'])
        paths = [image.image.path, image.thumbnail.path]
        self.assertTrue(all(os.path.exists(path) for path in paths))

        response = self.client.delete(f'{UPLOAD_URL}{image.pk}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ProductImage.objects.filter(pk=image.pk).exists())
        for path in paths:
            self.assertFalse(os.path.exists(path), f'{path} no se borró')

    def test_delete_keeps_working_when_the_file_is_locked(self):
        """A locked file must not strand the record: the user still deletes it."""
        image = ProductImage.objects.get(pk=self.upload(image=png_upload()).json()['id'])

        def refuse(self, save=False):
            raise PermissionError(32, 'El archivo está siendo utilizado por otro proceso.')

        # Mimic the Windows lock on every stored file of this model.
        with mock.patch.object(type(image.image), 'delete', refuse):
            response = self.client.delete(f'{UPLOAD_URL}{image.pk}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ProductImage.objects.filter(pk=image.pk).exists())

    def test_upload_rejects_a_missing_image(self):
        response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertIn('image', response.json())
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_upload_rejects_an_unknown_product(self):
        response = self.upload(product=Product(pk=999999), image=png_upload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_upload_rejects_a_disallowed_content_type(self):
        upload = SimpleUploadedFile('nota.txt', b'esto no es una imagen', content_type='text/plain')
        response = self.upload(image=upload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_upload_rejects_a_file_that_is_not_an_image(self):
        upload = SimpleUploadedFile('falso.png', b'GIF89a nope', content_type='image/png')
        response = self.upload(image=upload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_upload_rejects_an_oversized_file(self):
        upload = SimpleUploadedFile(
            'grande.png', b'\x00' * (10 * 1024 * 1024 + 1), content_type='image/png'
        )
        response = self.upload(image=upload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_anonymous_access_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.upload(image=png_upload())
        self.assertIn(response.status_code, {401, 403})
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_product_without_photos_reports_no_primary_image(self):
        response = self.client.get(f'/api/products/{self.product.pk}/')
        body = response.json()
        self.assertEqual(body['primary_image_url'], '')
        self.assertEqual(body['images'], [])


class ImageProcessingTestCase(TestCase):
    def test_processing_releases_the_file_handle(self):
        """Windows refuses ``os.remove`` while a PIL image still holds the file.

        This is the regression guard for the ``PermissionError`` that made
        deleting a photo return 500.
        """
        root = tempfile.mkdtemp(prefix='mayu-test-handle-')
        self.addCleanup(shutil.rmtree, root, True)
        path = os.path.join(root, 'entrada.png')
        with open(path, 'wb') as handle:
            handle.write(build_image((320, 240)))

        with open(path, 'rb') as source:
            processed = process_product_image(source)
        self.assertGreater(processed.size_bytes, 0)

        # Must not raise PermissionError on Windows.
        os.remove(path)
        self.assertFalse(os.path.exists(path))
