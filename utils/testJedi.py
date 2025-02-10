import jedi
import os
def main():
    file_path = "/mnt/ssd2/wangke/CR_data/repo/django-oscar/src/oscar/apps/catalogue/reviews/apps.py"
    script = jedi.Script(open(file_path).read(),path=file_path)
    definitions = script.goto(16,8)
    print(definitions)

if __name__ == '__main__':
    main()