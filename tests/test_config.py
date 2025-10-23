import random
from config_pynamic import *

def test_function_list_with_seed():
    random.seed(42)
    result = create_function_list(3)
    expected = [
        ['int', 0],
        ['float', 1, 'long'],
        ['long', 5, 'int', 'char *', 'int', 'char *', 'double']
    ]
    assert result == expected

def test_create_function_declaration():
    assert create_function_declaration("foo", ["void", 0]) == "void foo()"
    assert create_function_declaration("bar", ["int", 1, "float"]) == "int bar(float arg0)"
    assert create_function_declaration("baz", ["double", 3, "int", "float", "char"]) == "double baz(int arg0, float arg1, char arg2)"
    assert create_function_declaration("qux", ["int", 2, "int", "float", "char"]) == "int qux(int arg0, float arg1, char arg2)"

def test_create_function_call_with_seed():
    random.seed(42)

    function_name = "libutility0_fun"
    function_signature = ["float", 4, "int", "char *", "double", "long"]

    result = create_function_call(function_name, function_signature)

    # You can generate this expected value by running the function once with the seed
    expected = 'float libutility0_fun_val = libutility0_fun(309, "bicbbifg", -936434.641036, -809);'
    assert result == expected


def test_generate_utility_file_with_seed(mocker):
    # Set up mocks
    mock_create_list = mocker.patch("config_pynamic.create_function_list")
    mock_create_decl = mocker.patch("config_pynamic.create_function_declaration")
    mock_create_call = mocker.patch("config_pynamic.create_function_call")
    mock_open = mocker.patch("builtins.open", mocker.mock_open())

    # Mock random behavior
    mocker.patch("random.randint", return_value=2)
    mocker.patch("random.choices", side_effect=lambda seq, k: ['1'] * k)

    # Mock return values
    mock_create_list.return_value = [
        ["int", 2, "float", "char *"],
        ["float", 1, "int"]
    ]
    mock_create_decl.side_effect = lambda name, sig: f"{sig[0]} {name}({', '.join(sig[2:])})"
    mock_create_call.return_value = "int next_fun_call = next_fun();"

    # Run the function
    generate_utility_file(identity=1, avg_num_functions=4, name_length=0, print=True)

    # Check file writes
    handle = mock_open()
    written = "".join(call.args[0] for call in handle.write.call_args_list)
    print(written)

    assert "#include <stdio.h>" in written
    assert "int libutility1_fun0" in written
    assert "printf(\"In module libutility1 function libutility1_fun0" in written
    assert "return ret_val;" in written

