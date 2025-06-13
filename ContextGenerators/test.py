import jedi

# path = "/home/wangke/model/ContextGenerator/ContextGenerators/PythonContextGenerator.py"
path = "/home/wangke/model/ContextGenerator/ContextGenerators/test/test.py"

with open(path, 'r') as f:
    source_code = f.read()

script = jedi.Script(source_code, path=path)
# definitions = script.goto(89, 23) #Local
# definitions = script.goto(89, 35) 
# definitions = script.goto(97, 31)
# definitions = script.goto(103, 33)



# definitions = script.goto(9, 7) #call
# definitions = script.goto(12, 11) #传参 
# definitions = script.goto(13, 5) #传参  
definitions = script.goto(13, 7) #传参 + 调用


print(definitions)