# -*- coding: utf-8 -*-
# pylint: disable=attribute-defined-outside-init

from xmlrpc.client import Fault, ProtocolError

from django.contrib.auth.models import Permission
from tcms_api import xmlrpc

from tcms.rpc.tests.utils import XmlrpcAPIBaseTest
from tcms.testcases.models import TestCase
from tcms.tests import remove_perm_from_user
from tcms.tests.factories import (CategoryFactory, ComponentFactory,
                                  ProductFactory, TagFactory, TestCaseFactory,
                                  TestPlanFactory, UserFactory, VersionFactory)


class TestNotificationRemoveCC(XmlrpcAPIBaseTest):
    """ Tests the XML-RPC testcase.notication_remove_cc method """

    def _fixture_setup(self):
        super(TestNotificationRemoveCC, self)._fixture_setup()

        self.default_cc = 'example@MrSenko.com'
        self.testcase = TestCaseFactory()
        self.testcase.emailing.add_cc(self.default_cc)

    def tearDown(self):
        super(TestNotificationRemoveCC, self).tearDown()
        self.rpc_client.exec.Auth.logout()

    def test_remove_existing_cc(self):
        # initially testcase has the default CC listed
        # and we issue XMLRPC request to remove the cc
        self.rpc_client.exec.TestCase.remove_notification_cc(self.testcase.pk, [self.default_cc])

        # now verify that the CC email has been removed
        self.testcase.emailing.refresh_from_db()
        self.assertEqual([], self.testcase.emailing.get_cc_list())


class TestFilterCases(XmlrpcAPIBaseTest):

    def _fixture_setup(self):
        super(TestFilterCases, self)._fixture_setup()

        self.tester = UserFactory(username='great tester')
        self.product = ProductFactory(name='StarCraft')
        self.version = VersionFactory(value='0.1', product=self.product)
        self.plan = TestPlanFactory(name='Test product.get_cases',
                                    author=self.tester,
                                    product=self.product,
                                    product_version=self.version)
        self.case_category = CategoryFactory(product=self.product)
        self.cases_count = 10
        self.cases = []
        for _ in range(self.cases_count):
            test_case = TestCaseFactory(
                category=self.case_category,
                author=self.tester,
                reviewer=self.tester,
                default_tester=None,
                plan=[self.plan])
            self.cases.append(test_case)

    def test_filter_by_product_id(self):
        cases = self.rpc_client.exec.TestCase.filter({'category__product': self.product.pk})
        self.assertIsNotNone(cases)
        self.assertEqual(len(cases), self.cases_count)


class TestUpdate(XmlrpcAPIBaseTest):

    def _fixture_setup(self):
        super(TestUpdate, self)._fixture_setup()

        self.testcase = TestCaseFactory(text='')

    def test_update_text_and_product(self):
        self.assertEqual('', self.testcase.text)

        # update the test case
        updated = self.rpc_client.exec.TestCase.update(  # pylint: disable=objects-update-used
            self.testcase.pk,
            {
                'summary': 'This was updated',
                'text': 'new TC text',
            }
        )
        self.testcase.refresh_from_db()  # refresh before assertions

        self.assertEqual(updated['case_id'], self.testcase.pk)
        self.assertEqual('This was updated', self.testcase.summary)
        self.assertEqual('new TC text', self.testcase.text)


class TestAddTag(XmlrpcAPIBaseTest):

    def _fixture_setup(self):
        super()._fixture_setup()

        self.testcase = TestCaseFactory()

        self.tag1 = TagFactory()
        self.tag2 = TagFactory()

    def test_add_tag(self):
        self.rpc_client.exec.TestCase.add_tag(self.testcase.pk, self.tag1.name)
        tag_exists = TestCase.objects.filter(pk=self.testcase.pk, tag__pk=self.tag1.pk).exists()
        self.assertTrue(tag_exists)

    def test_add_tag_without_permissions(self):
        unauthorized_user = UserFactory()
        unauthorized_user.set_password('api-testing')
        unauthorized_user.save()

        unauthorized_user.user_permissions.add(*Permission.objects.all())
        remove_perm_from_user(unauthorized_user, 'testcases.add_testcasetag')

        rpc_client = xmlrpc.TCMSXmlrpc(unauthorized_user.username,
                                       'api-testing',
                                       '%s/xml-rpc/' % self.live_server_url).server

        with self.assertRaisesRegex(ProtocolError, '403 Forbidden'):
            rpc_client.TestCase.add_tag(self.testcase.pk, self.tag1.name)

        # tags were not modified
        tag_exists = TestCase.objects.filter(pk=self.testcase.pk, tag__pk=self.tag1.pk).exists()
        self.assertFalse(tag_exists)


class TestRemoveTag(XmlrpcAPIBaseTest):

    def _fixture_setup(self):
        super()._fixture_setup()

        self.tag0 = TagFactory()
        self.tag1 = TagFactory()

        self.testcase = TestCaseFactory()
        self.testcase.add_tag(self.tag0)

    def test_remove_tag(self):
        self.rpc_client.exec.TestCase.remove_tag(self.testcase.pk, self.tag0.name)
        tag_exists = TestCase.objects.filter(pk=self.testcase.pk, tag__pk=self.tag0.pk).exists()
        self.assertFalse(tag_exists)

    def test_remove_tag_without_permissions(self):
        unauthorized_user = UserFactory()
        unauthorized_user.set_password('api-testing')
        unauthorized_user.save()

        unauthorized_user.user_permissions.add(*Permission.objects.all())
        remove_perm_from_user(unauthorized_user, 'testcases.delete_testcasetag')

        rpc_client = xmlrpc.TCMSXmlrpc(unauthorized_user.username,
                                       'api-testing',
                                       '%s/xml-rpc/' % self.live_server_url).server

        with self.assertRaisesRegex(ProtocolError, '403 Forbidden'):
            rpc_client.TestCase.remove_tag(self.testcase.pk, self.tag0.name)

        # tags were not modified
        tag_exists = TestCase.objects.filter(pk=self.testcase.pk, tag__pk=self.tag0.pk).exists()
        self.assertTrue(tag_exists)

        tag_exists = TestCase.objects.filter(pk=self.testcase.pk, tag__pk=self.tag1.pk).exists()
        self.assertFalse(tag_exists)


class TestAddComponent(XmlrpcAPIBaseTest):

    def _fixture_setup(self):
        super()._fixture_setup()
        self.test_case = TestCaseFactory()
        self.good_component = ComponentFactory(product=self.test_case.category.product)
        self.bad_component = ComponentFactory()

    def test_add_component_from_same_product_is_allowed(self):
        result = self.rpc_client.exec.TestCase.add_component(self.test_case.pk,
                                                             self.good_component.name)
        self.assertEqual(result['component'][0], self.good_component.pk)

    def test_add_component_from_another_product_is_not_allowed(self):
        with self.assertRaisesRegex(Fault, 'Component matching query does not exist'):
            self.rpc_client.exec.TestCase.add_component(self.test_case.pk, self.bad_component.name)
