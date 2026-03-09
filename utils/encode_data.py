import base64
import os
#
main_dir = os.getcwd().split('utils')[0]
#
for file in os.listdir(os.path.join(main_dir, 'data')):
    with open(os.path.join(main_dir, 'data', file), 'rb') as f:
        encoded = base64.b64encode(f.read()).decode()
    print()
    print(f'--------- {file} ---------')
    print(encoded)