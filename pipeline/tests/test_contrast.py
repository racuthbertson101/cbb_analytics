from pipeline.tools.contrast import main


def test_text_tokens_meet_wcag_aa():
    assert main() == 0
