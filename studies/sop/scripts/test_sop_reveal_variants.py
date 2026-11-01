from scripts.sop_reveal_variants import main


def test_variants_table_has_one_row_per_variant(capsys):
    assert main(['--days', '5', '--seed', '1']) == 0
    out = capsys.readouterr().out
    assert out.count('\n| ') >= 8 and '+pending, G=5 (T5)' in out
