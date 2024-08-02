# ContextGenerator
A context generator for code review

## Run

```bash
#requirements
pip install tree-sitter tree-sitter-c tree-sitter-cpp tree-sitter-c-sharp tree-sitter-go tree-sitter-java tree-sitter-javascript tree-sitter-python tree-sitter-ruby

#repo:demo_repo
cd repo
git clone https://github.com/spotify/luigi.git
cd ..

#在项目根目录下运行ContextGenerator.py
```

### Postgres Config

```python
db_config = {
    'dbname': 'HCGGraph',
    'user': 'user',
    'password': '123456',
    'host': 'localhost',
    'port': '5432'
}
#新建HCGGraph的数据库
#可以从cacr.csv导入数据到postgres
#需要设置数据库的读写权限：HCGGraph->properties->Security
```

