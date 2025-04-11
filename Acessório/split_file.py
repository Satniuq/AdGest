import math

input_file = 'codigo_concatenado.txt'
num_parts = 5

with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

total_lines = len(lines)
chunk_size = math.ceil(total_lines / num_parts)

for i in range(num_parts):
    start = i * chunk_size
    end = start + chunk_size
    part_lines = lines[start:end]
    output_file = f'parte_{i+1}.txt'
    with open(output_file, 'w', encoding='utf-8') as f_out:
         f_out.writelines(part_lines)
    print(f'Criado: {output_file}')
