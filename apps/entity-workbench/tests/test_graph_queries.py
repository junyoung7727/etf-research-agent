import unittest
from backend.graph_queries import interface_traversal
from backend.interface_types import source_catalog
from backend.view_design import read_catalog


class GraphQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.interfaces={i['name']:i for i in source_catalog()['catalog']['interfaces']}
        cls.catalog=read_catalog()

    def test_actor_batch_preserves_type_and_roles_without_data_interpolation(self):
        unusual="x' MATCH (n) DELETE n //"
        query,params=interface_traversal(self.interfaces['Actor'],'participatesIn',
            [{'type':'Company','id':unusual},{'type':'Organization','id':'org1'}],self.catalog,{'roleCode':'SUPPLIER'})
        self.assertNotIn(unusual,query)
        self.assertIn(unusual,params['ids_0'])
        self.assertIn('UNION ALL',query)  # Distinct participation records must survive.
        self.assertIn('roleCode',query)
        self.assertIn('linkKey',query)
        self.assertIn('objectType',query)

    def test_security_reverse_mapping_is_followed(self):
        query,_=interface_traversal(self.interfaces['Security'],'heldIn',[],self.catalog)
        self.assertIn('<-[r:',query)
        self.assertIn('ETFHolding',query)

    def test_unknown_role_filter_and_untyped_id_are_rejected(self):
        with self.assertRaises(ValueError):
            interface_traversal(self.interfaces['Actor'],'participatesIn',['company1'],self.catalog)
        with self.assertRaises(ValueError):
            interface_traversal(self.interfaces['Actor'],'participatesIn',[],self.catalog,{'guessedRole':'buyer'})
