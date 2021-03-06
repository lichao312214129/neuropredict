import sys
from sys import version_info

import numpy as np
from os.path import dirname, abspath

sys.dont_write_bytecode = True

if __name__ == '__main__' and __package__ is None:
    parent_dir = dirname(dirname(abspath(__file__)))
    sys.path.append(parent_dir)

if version_info.major > 2:
    from neuropredict.utils import balanced_accuracy
else:
    raise NotImplementedError('neuropredict supports only Python 3+.')


def test_balanced_accuracy():
    """Tests ensure the accuracy of accuracy calculations!"""

    num_trials = 10

    for num_classes in np.random.randint(2, 100, num_trials):
        cm_100 = np.zeros((num_classes, num_classes), int)
        # no errors! sizes are imbalanced
        np.fill_diagonal(cm_100, np.random.randint(10, 100, num_classes))
        if not np.isclose(balanced_accuracy(cm_100), 1.0):
            raise ArithmeticError('accuracy calculations on perfect classifier '
                                  'does not return 100% accuracy!!')

        cm_100perc_wrong = np.random.randint(10, 100, (num_classes, num_classes))
        # ALL errors! sizes are imbalanced
        np.fill_diagonal(cm_100perc_wrong, 0.0)
        if not np.isclose(balanced_accuracy(cm_100perc_wrong), 0.0):
            raise ArithmeticError('accuracy calculations on 100% wrong classifier '
                                  'does not return 0% accuracy!!')

        cm = np.random.randint(10, 100, (num_classes, num_classes)).astype('float64')
        np.fill_diagonal(cm, 0)
        class_sizes_without_diag_elemeent = cm.sum(axis=1)
        chosen_accuracy = np.round(np.random.rand(num_classes), decimals=3)
        factor = chosen_accuracy / (1.0 - chosen_accuracy)
        # filling the diag in order to reach certain level of chosen accuracy
        diag_values = np.around(class_sizes_without_diag_elemeent * factor).astype('float64')
        np.fill_diagonal(cm, diag_values)
        computed_acc = balanced_accuracy(cm)
        expected_acc = np.mean(chosen_accuracy)
        if not np.isclose(computed_acc, expected_acc, atol=1e-4):
            raise ArithmeticError('accuracy calculations do not match the expected!!\n'
                                  ' Expected : {:.8f}\n'
                                  ' Estimated: {:.8f}\n'
                                  ' Differ by: {:.8f}\n'.format(expected_acc, computed_acc,
                                                                expected_acc - computed_acc))


test_balanced_accuracy()
