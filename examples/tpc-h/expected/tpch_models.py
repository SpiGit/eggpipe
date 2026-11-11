from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    c_custkey: int
    c_name: str = Field(max_length=25)
    c_address: str = Field(max_length=40)
    c_nationkey: int
    c_phone: str = Field(max_length=15)
    c_acctbal: Decimal = Field(max_digits=15, decimal_places=2)
    c_mktsegment: str = Field(max_length=10)
    c_comment: str = Field(max_length=117)


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    l_orderkey: int
    l_partkey: int
    l_suppkey: int
    l_linenumber: int
    l_quantity: Decimal = Field(max_digits=15, decimal_places=2)
    l_extendedprice: Decimal = Field(max_digits=15, decimal_places=2)
    l_discount: Decimal = Field(max_digits=15, decimal_places=2)
    l_tax: Decimal = Field(max_digits=15, decimal_places=2)
    l_returnflag: str = Field(max_length=1)
    l_linestatus: str = Field(max_length=1)
    l_shipdate: date
    l_commitdate: date
    l_receiptdate: date
    l_shipinstruct: str = Field(max_length=25)
    l_shipmode: str = Field(max_length=10)
    l_comment: str = Field(max_length=44)


class Nation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_nationkey: int
    n_name: str = Field(max_length=25)
    n_regionkey: int
    n_comment: str = Field(max_length=152)


class Orders(BaseModel):
    model_config = ConfigDict(extra="forbid")
    o_orderkey: int
    o_custkey: int
    o_orderstatus: str = Field(max_length=1)
    o_totalprice: Decimal = Field(max_digits=15, decimal_places=2)
    o_orderdate: date
    o_orderpriority: str = Field(max_length=15)
    o_clerk: str = Field(max_length=15)
    o_shippriority: int
    o_comment: str = Field(max_length=79)


class Part(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p_partkey: int
    p_name: str = Field(max_length=55)
    p_mfgr: str = Field(max_length=25)
    p_brand: str = Field(max_length=10)
    p_type: str = Field(max_length=25)
    p_size: int
    p_container: str = Field(max_length=10)
    p_retailprice: Decimal = Field(max_digits=15, decimal_places=2)
    p_comment: str = Field(max_length=23)


class PartSupp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ps_partkey: int
    ps_suppkey: int
    ps_availqty: int
    ps_supplycost: Decimal = Field(max_digits=15, decimal_places=2)
    ps_comment: str = Field(max_length=199)


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")
    r_regionkey: int
    r_name: str = Field(max_length=25)
    r_comment: str = Field(max_length=152)


class Supplier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    s_suppkey: int
    s_name: str = Field(max_length=25)
    s_address: str = Field(max_length=40)
    s_nationkey: int
    s_phone: str = Field(max_length=15)
    s_acctbal: Decimal = Field(max_digits=15, decimal_places=2)
    s_comment: str = Field(max_length=101)


__all__ = ["Customer", "LineItem", "Nation", "Orders", "Part", "PartSupp", "Region", "Supplier"]
