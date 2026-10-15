from accesscast.seeds import derive_seed


def test_derive_seed_is_stable_and_label_sensitive():
    assert derive_seed(20261018, "ad.en.0001:run0") == derive_seed(20261018, "ad.en.0001:run0")
    assert derive_seed(20261018, "ad.en.0001:run0") != derive_seed(20261018, "ad.en.0001:run1")
    assert 0 <= derive_seed(1, "x") < 2**32
