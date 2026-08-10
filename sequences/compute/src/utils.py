#################################################################################
# MIT License                                                                   #
#                                                                               #
# Copyright (c) 2022 Wilson Lam                                                 #
#                                                                               #
# Permission is hereby granted, free of charge, to any person obtaining a copy  #
# of this software and associated documentation files (the "Software"), to deal`#
# in the Software without restriction, including without limitation the rights  #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell     #
# copies of the Software, and to permit persons to whom the Software is         #
# furnished to do so, subject to the following conditions:                      #
#                                                                               #
# The above copyright notice and this permission notice shall be included in all#
# copies or substantial portions of the Software.                               #
#                                                                               #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR    #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,      #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE   #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER        #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE #
# SOFTWARE.                                                                     #
#################################################################################

import pandas as pd
from .combinations import list_possible_combinations
from .similarity import dsc, jaccard, ssc
from .variability import execution_entropy
from .mlcs import mlcs_leveled_DAG

FUNCTIONS = {
    "mlcs" : mlcs_leveled_DAG,
    "entropy" : execution_entropy,
    "dice" : dsc,
    "jaccard" : jaccard,
    "overlap" : ssc,
    "permute" : list_possible_combinations
}

def _create_temp_sym(unique_chr):
    assert 80 >= len(unique_chr) > 1, \
        "can only handle 2 to 80 characters"
    src_tmp = {c : chr(i+39) for i, c in enumerate(unique_chr)}
    tmp_src = {v : k for k,v in src_tmp.items()}
    return src_tmp, tmp_src


def compute_metric(csv_file, measure, sep):

    function = FUNCTIONS.get(measure)
    assert function, \
        f"""invalid measurement {measure}, valid options:
        {FUNCTIONS.keys()}
        """
    
    data = pd.read_csv(csv_file, sep=sep, header=None)


    def mlcs(data):

        unique_chars = data.iloc[0].values[0].split('-')
        src_tmp, tmp_src = _create_temp_sym(unique_chars)
        input_chars = [src_tmp[c] for c in unique_chars]
        data = data.applymap(lambda x : ''.join([src_tmp[c] for c in x.split('-')]))
        output = function(list(data.values.flatten()), input_chars, findall=True)
        output = ['-'.join([tmp_src[c] for c in s]) for s in output]

        return output

    assert len(data) > 0, "empty data."

    if measure in ['dice', 'jaccard', 'overlap', 'permute']:
        assert data.shape[1] == 2, \
            f"`{measure}` requires two columns of data, got {data.shape[1]} column(s)."
    
    
    if measure == 'mlcs':

        assert data.shape[1] == 1, \
        f"`{measure}` requires only one column of data, got {data.shape[1]} column(s)."

        assert len(data.iloc[0].values[0].split('-')) > 1, \
        f"Unable to read sequences. For `{measure}` please use `-` as the separator of sequence data."

        if measure == 'mlcs':
            return measure, mlcs(data)
        return measure, data.applymap(function)    
    return measure, data.apply(function)


    


    


