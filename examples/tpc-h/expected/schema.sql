CREATE TABLE public.customer (
    c_custkey integer NOT NULL,
    c_name varchar(25) NOT NULL,
    c_address varchar(40) NOT NULL,
    c_nationkey integer NOT NULL,
    c_phone char(15) NOT NULL,
    c_acctbal decimal(15,2) NOT NULL,
    c_mktsegment char(10) NOT NULL,
    c_comment varchar(117) NOT NULL,
    CONSTRAINT customer_pkey PRIMARY KEY (c_custkey)
);

CREATE TABLE public.lineitem (
    l_orderkey integer NOT NULL,
    l_partkey integer NOT NULL,
    l_suppkey integer NOT NULL,
    l_linenumber integer NOT NULL,
    l_quantity decimal(15,2) NOT NULL,
    l_extendedprice decimal(15,2) NOT NULL,
    l_discount decimal(15,2) NOT NULL,
    l_tax decimal(15,2) NOT NULL,
    l_returnflag char(1) NOT NULL,
    l_linestatus char(1) NOT NULL,
    l_shipdate date NOT NULL,
    l_commitdate date NOT NULL,
    l_receiptdate date NOT NULL,
    l_shipinstruct char(25) NOT NULL,
    l_shipmode char(10) NOT NULL,
    l_comment varchar(44) NOT NULL,
    CONSTRAINT lineitem_pkey PRIMARY KEY (l_orderkey, l_linenumber)
);

CREATE TABLE public.nation (
    n_nationkey integer NOT NULL,
    n_name char(25) NOT NULL,
    n_regionkey integer NOT NULL,
    n_comment varchar(152) NOT NULL,
    CONSTRAINT nation_pkey PRIMARY KEY (n_nationkey)
);

CREATE TABLE public.orders (
    o_orderkey integer NOT NULL,
    o_custkey integer NOT NULL,
    o_orderstatus char(1) NOT NULL,
    o_totalprice decimal(15,2) NOT NULL,
    o_orderdate date NOT NULL,
    o_orderpriority char(15) NOT NULL,
    o_clerk char(15) NOT NULL,
    o_shippriority integer NOT NULL,
    o_comment varchar(79) NOT NULL,
    CONSTRAINT orders_pkey PRIMARY KEY (o_orderkey)
);

CREATE TABLE public.part (
    p_partkey integer NOT NULL,
    p_name varchar(55) NOT NULL,
    p_mfgr char(25) NOT NULL,
    p_brand char(10) NOT NULL,
    p_type varchar(25) NOT NULL,
    p_size integer NOT NULL,
    p_container char(10) NOT NULL,
    p_retailprice decimal(15,2) NOT NULL,
    p_comment varchar(23) NOT NULL,
    CONSTRAINT part_pkey PRIMARY KEY (p_partkey)
);

CREATE TABLE public.partsupp (
    ps_partkey integer NOT NULL,
    ps_suppkey integer NOT NULL,
    ps_availqty integer NOT NULL,
    ps_supplycost decimal(15,2) NOT NULL,
    ps_comment varchar(199) NOT NULL,
    CONSTRAINT partsupp_pkey PRIMARY KEY (ps_partkey, ps_suppkey)
);

CREATE TABLE public.region (
    r_regionkey integer NOT NULL,
    r_name char(25) NOT NULL,
    r_comment varchar(152) NOT NULL,
    CONSTRAINT region_pkey PRIMARY KEY (r_regionkey)
);

CREATE TABLE public.supplier (
    s_suppkey integer NOT NULL,
    s_name char(25) NOT NULL,
    s_address varchar(40) NOT NULL,
    s_nationkey integer NOT NULL,
    s_phone char(15) NOT NULL,
    s_acctbal decimal(15,2) NOT NULL,
    s_comment varchar(101) NOT NULL,
    CONSTRAINT supplier_pkey PRIMARY KEY (s_suppkey)
);

ALTER TABLE public.customer ADD CONSTRAINT customer_c_nationkey_fkey FOREIGN KEY (c_nationkey) REFERENCES public.nation (n_nationkey);
ALTER TABLE public.lineitem ADD CONSTRAINT lineitem_l_orderkey_fkey FOREIGN KEY (l_orderkey) REFERENCES public.orders (o_orderkey);
ALTER TABLE public.lineitem ADD CONSTRAINT lineitem_l_partkey_l_suppkey_fkey FOREIGN KEY (l_partkey, l_suppkey) REFERENCES public.partsupp (ps_partkey, ps_suppkey);
ALTER TABLE public.nation ADD CONSTRAINT nation_n_regionkey_fkey FOREIGN KEY (n_regionkey) REFERENCES public.region (r_regionkey);
ALTER TABLE public.orders ADD CONSTRAINT orders_o_custkey_fkey FOREIGN KEY (o_custkey) REFERENCES public.customer (c_custkey);
ALTER TABLE public.partsupp ADD CONSTRAINT partsupp_ps_partkey_fkey FOREIGN KEY (ps_partkey) REFERENCES public.part (p_partkey);
ALTER TABLE public.partsupp ADD CONSTRAINT partsupp_ps_suppkey_fkey FOREIGN KEY (ps_suppkey) REFERENCES public.supplier (s_suppkey);
ALTER TABLE public.supplier ADD CONSTRAINT supplier_s_nationkey_fkey FOREIGN KEY (s_nationkey) REFERENCES public.nation (n_nationkey);
