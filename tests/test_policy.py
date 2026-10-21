from backend.policy import check_chat_request, validate_fixed_query

def test_blocks_destructive_request():
    assert check_chat_request("Please drop the production database")[0] is False

def test_allows_read_only_question():
    assert check_chat_request("How can I investigate SQL Server blocking?")[0] is True

def test_allows_select():
    assert validate_fixed_query("SELECT name FROM sys.databases")

def test_blocks_update():
    assert not validate_fixed_query("UPDATE users SET role='admin'")

def test_blocks_multiple_statements():
    assert not validate_fixed_query("SELECT 1; DROP TABLE x")
