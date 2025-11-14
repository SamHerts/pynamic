import random

import pytest

from config_pynamic import *

@pytest.fixture(autouse=True)
def set_random_seed():
    random.seed(42)

def test_create_function_list():
    result = create_function_list(3)
    expected = [
        ['int', 0],
        ['float', 1, 'long'],
        ['long', 5, 'int', 'char *', 'int', 'char *', 'double']
    ]
    assert result == expected

def test_generate_function_names():
    base_name = "my_base_name"
    avg_num_functions = 10
    name_length = 0
    gen_functions = generate_function_names(base_name, avg_num_functions, name_length)
    assert len(gen_functions) == 15
    assert gen_functions[0] == ("my_base_name_fun0", ['int', 0])

    name_length = 5
    gen_functions = generate_function_names(base_name, avg_num_functions, name_length)

    assert len(gen_functions) == 5
    assert gen_functions[4] == ("my_base_name_fun445391", ['long', 3, 'double', 'float', 'char *'])

def test_create_function_declaration():
    assert create_function_declaration("foo", ["void", 0]) == "void\tfoo()"
    assert create_function_declaration("bar", ["int", 1, "float"]) == "int \tbar(float arg0)"
    assert create_function_declaration("baz", ["double", 3, "int", "float", "char"]) == "double\tbaz(int arg0, float arg1, char arg2)"
    assert create_function_declaration("qux", ["int", 2, "int", "float", "char"]) == "int \tqux(int arg0, float arg1, char arg2)"

def test_create_function_call():
    function_name = "libutility0_fun"
    function_signature = ["float", 4, "int", "char *", "double", "long"]

    result = create_function_call(function_name, function_signature)

    # You can generate this expected value by running the function once with the seed
    expected = 'float libutility0_fun_val = libutility0_fun(309, "bicbbifg", -936434.641036, -809);'
    assert result == expected


# def test_generate_utility_file(mocker):
#     # Set up mocks
#     mock_generate_function_names = mocker.patch(
#         __name__ + ".generate_function_names",
#         return_value=[
#             ("libutility1_fun0", ["int", "float", "char *"]),
#             ("libutility1_fun1", ["float", "int"])
#         ]
#     )
#     mock_create_decl = mocker.patch(__name__ + ".create_function_declaration")
#     mock_create_call = mocker.patch("config_pynamic.create_function_call")
#     mock_open = mocker.patch("builtins.open", mocker.mock_open())
#
#     # Mock random behavior
#     mocker.patch("random.randint", return_value=2)
#     mocker.patch("random.choices", side_effect=lambda seq, k: ['1'] * k)
#
#     mock_create_decl.side_effect = lambda name, sig: f"{sig[0]} {name}({', '.join(sig[2:])})"
#     mock_create_call.return_value = "int next_fun_call = next_fun();"
#
#     # Run the function
#     generate_utility_file(identity=1, avg_num_functions=4, name_length=0, print=True)
#
#     # Check file writes
#     handle = mock_open()
#     written = "".join(call.args[0] for call in handle.write.call_args_list)
#     # print("\n\n" + written)
#
#
#     assert "#include <stdio.h>" in written
#     assert "int libutility1_fun0" in written
#     assert "printf(\"In module libutility1 function libutility1_fun0" in written
#     assert "return ret_val;" in written

