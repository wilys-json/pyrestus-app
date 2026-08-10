
from pydicom import dcmread
from datetime import datetime

def format_filename(name='', pid='', start_time='', **kwargs)->str:

    elements = [name, pid, start_time]

    remarks = kwargs.get('remarks', '')
    start_time = str(start_time)
    start_time = (start_time if len(start_time) == 0
               else "".join("_".join(start_time.split(" ")).split(":")))

    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    filename = (f'{name}-{pid}-{start_time}{remarks}'
                if all(elements)
                else timestamp)

    return filename


def format_sequence_info(dicom_file):
    sequence_info = dict()
    for item in dcmread(dicom_file).SequenceOfUltrasoundRegions[0].iterall():
        sequence_info.update({item.name:item.value})
    return sequence_info
