
from __future__ import print_function

import argparse
import os
import sys
import textwrap
import traceback
import warnings
from sys import version_info
from os.path import join as pjoin, exists as pexists, abspath, realpath, basename
import numpy as np

from pyradigm.utils import load_dataset

# the order of import is very important to avoid circular imports
from neuropredict import __version__
from neuropredict import config_neuropredict as cfg
from neuropredict.base import organize_inputs, get_parser_base
from neuropredict import rhst, visualize
from neuropredict.freesurfer import (aseg_stats_subcortical,
                                     aseg_stats_whole_brain)
from neuropredict.io import (get_metadata, get_features,
                             get_metadata_in_pyradigm,
                             get_data_matrix, get_dir_of_dirs, get_pyradigm,
                             get_arff,
                             saved_dataset_matches)
from neuropredict.utils import (check_paths, uniq_combined_name,
                                check_num_procs,
                                sub_group_identifier, save_options, load_options,
                                validate_feature_selection_size,
                                validate_impute_strategy,
                                make_dataset_filename, not_unspecified,
                                check_classifier, print_options)

def get_parser_regress():
    """"""

    parser, user_feat_args, cv_args, pipeline_args, vis_args, comp_args = \
        get_parser_base()

    help_regressor = textwrap.dedent("""

    String specifying one of the implemented regressors. 
    (Regressors are carefully chosen to allow for the comprehensive report 
    provided by neuropredict).

    Default: 'RandomForestRegressor'

    """)

    pipeline_args.add_argument("-e", "--regressor", action="store",
                               dest="regressor",
                               default=cfg.default_regressor, help=help_regressor,
                               choices=cfg.regressor_choices, type=str.lower)

    return parser


def parse_args():
    """Parser/validator for the cmd line args."""

    parser = get_parser_regress()

    if len(sys.argv) < 2:
        print('Too few arguments!')
        parser.print_help()
        parser.exit(1)

    # parsing
    try:
        user_args = parser.parse_args()
    except:
        parser.exit(1)

    if len(sys.argv) == 3:
        # only if no features were specified to be assessed
        if not any(not_unspecified(getattr(user_args, attr))
               for attr in ('user_feature_paths', 'data_matrix_paths',
                            'pyradigm_paths', 'arff_paths')):

            if not_unspecified(user_args.print_opt_dir) and user_args.print_opt_dir:
                run_dir = realpath(user_args.print_opt_dir)
                print_options(run_dir)

            if not_unspecified(user_args.make_vis):
                out_dir = realpath(user_args.make_vis)
                res_path = pjoin(out_dir, cfg.file_name_results)
                if pexists(out_dir) and pexists(res_path):
                    if not_unspecified(user_args.make_vis):
                        print('\n\nSaving the visualizations to \n{}'.format(out_dir))
                        make_visualizations(res_path, out_dir)
                else:
                    raise ValueError('Given folder does not exist, '
                                     'or has no results file!')

            sys.exit(0)

    user_feature_paths, user_feature_type, fs_subject_dir, meta_data_path, \
        meta_data_format = organize_inputs(user_args)

    if not meta_data_path:
        if user_args.meta_file is not None:
            meta_file = abspath(user_args.meta_file)
            if not pexists(meta_file):
                raise IOError("Meta data file doesn't exist.")
        else:
            raise ValueError('Metadata file must be provided '
                             'when not using pyradigm/ARFF inputs.')

        sample_ids, classes = get_metadata(meta_file)
    else:
        print('Using meta data from:\n{}'.format(meta_data_path))
        sample_ids, classes = get_metadata_in_pyradigm(meta_data_path,
                                                       meta_data_format)

    if user_args.out_dir is not None:
        out_dir = realpath(user_args.out_dir)
    else:
        out_dir = pjoin(realpath(os.getcwd()), cfg.output_dir_default)

    try:
        os.makedirs(out_dir, exist_ok=True)
    except:
        raise IOError('Output folder could not be created.')

    train_perc = np.float32(user_args.train_perc)
    if not ( 0.01 <= train_perc <= 0.99):
        raise ValueError("Training percentage {} out of bounds "
                         "- must be >= 0.01 and <= 0.99".format(train_perc))

    num_rep_cv = np.int64(user_args.num_rep_cv)
    if num_rep_cv < 10:
        raise ValueError("Atleast 10 repetitions of CV is recommened.")

    num_procs = check_num_procs(user_args.num_procs)


    feature_selection_size = validate_feature_selection_size(
            user_args.num_features_to_select)

    impute_strategy = validate_impute_strategy(user_args.impute_strategy)

    grid_search_level = user_args.gs_level.lower()
    if grid_search_level not in cfg.GRIDSEARCH_LEVELS:
        raise ValueError('Unrecognized level of grid search. Valid choices: {}'
                         ''.format(cfg.GRIDSEARCH_LEVELS))

    classifier = check_classifier(user_args.classifier)
    feat_select_method = user_args.feat_select_method.lower()

    # saving the validated and expanded values to disk for later use.
    options_to_save = [sample_ids, classes, out_dir, user_feature_paths,
                       user_feature_type, fs_subject_dir, train_perc, num_rep_cv,
                       feature_selection_size, num_procs,
                       grid_search_level, classifier, feat_select_method]
    options_path = save_options(options_to_save, out_dir)

    return sample_ids, classes, out_dir, options_path, \
           user_feature_paths, user_feature_type, fs_subject_dir, \
           train_perc, num_rep_cv, \
           feature_selection_size, impute_strategy, num_procs, \
           grid_search_level, classifier, feat_select_method


def cli():
    """
    Main entry point.

    """

    subjects, classes, out_dir, options_path, user_feature_paths, user_feature_type, \
        fs_subject_dir, train_perc, num_rep_cv, \
        feature_selection_size, impute_strategy, num_procs, \
        grid_search_level, classifier, feat_select_method = parse_args()

    print('Running neuropredict version {}'.format(__version__))
    prepare_and_run(subjects, classes, out_dir, options_path,
                    user_feature_paths, user_feature_type, fs_subject_dir,
                    train_perc, num_rep_cv, feature_selection_size, impute_strategy,
                    num_procs,
                    grid_search_level, classifier, feat_select_method)

    return


def prepare_and_run(subjects, classes, out_dir, options_path,
                    user_feature_paths, user_feature_type, fs_subject_dir,
                    train_perc, num_rep_cv, feature_selection_size, impute_strategy,
                    num_procs,
                    grid_search_level, classifier, feat_select_method):
    """"""
    pass


def make_visualizations():
    pass

class RegressionExperiment:
    """
    Class defining an neuropredict experiment to be run.

    Encapsulates all the details necessary for execution,
        hence easing the save/load/decide workflow.

    """


    def __init__(self,
                 datasets,
                 pred_model=cfg.default_classifier,
                 dim_red_method=cfg.default_feat_select_method,
                 reduced_dim=cfg.default_num_features_to_select,
                 train_perc=cfg.default_train_perc,
                 num_rep_cv=cfg.default_num_repetitions,
                 grid_search_level=cfg.GRIDSEARCH_LEVEL_DEFAULT,
                 sub_groups=None,
                 num_procs=cfg.DEFAULT_NUM_PROCS):

        self.datasets = datasets
        self.pred_model = pred_model
        self.dim_red_method = dim_red_method
        self.reduced_dim = reduced_dim
        self.train_perc = train_perc
        self.num_rep_cv = num_rep_cv
        self.grid_search_level = grid_search_level
        self.sub_groups = sub_groups
        self.num_procs = num_procs


    def run(self):
        """Main method that crunches the calculations."""



if __name__ == '__main__':
    cli()