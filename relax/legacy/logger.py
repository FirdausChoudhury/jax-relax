# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/legacy/04a_logger.ipynb.

# %% ../../nbs/legacy/04a_logger.ipynb 3
from __future__ import annotations
from .import_essentials import *
from collections import defaultdict

# %% auto 0
__all__ = ['Logger']

# %% ../../nbs/legacy/04a_logger.ipynb 4
# class TensorboardLogger:
class Logger:
    _last_logs: Dict = dict()

    def __init__(self, log_dir: Union[str, Path], name: str, on_step: bool = False):
        self._log_dir = log_dir
        self._on_step = on_step
        # self.experiment = test_tube.Experiment(name=name, save_dir=log_dir)
        self.experiment = None
        self._epoch_logs = defaultdict(list)

    @property
    def log_dir(self):
        return self._log_dir
        # name = self.experiment.name
        # version = self.experiment.version
        # return self.experiment.get_data_path(name, version)

    def save_hyperparams(self, hparams: dict | BaseParser):
        pass
        # if issubclass(type(hparams), BaseParser): 
        #     hparams = hparams.dict()
        # if isinstance(hparams, dict):
        #     self.experiment.tag(hparams)
        # else:
        #     raise ValueError(f"hparams should be either `dict`, or a sublcass of `BaseParser`",
        #         f"but got {type(hparams)}.")            
        

    def log(self, name: str, value: Any):
        self.log_dict({name: value})

    def log_dict(self, dictionary: Dict[str, float]):
        for k, v in dictionary.items():
            self._epoch_logs[k].append(v)

        # log to test_tube if on_step is True
        # if self._on_step:
        #     self.experiment.log(dictionary)
        self._last_logs = dictionary

    def get_last_logs(self):
        return self._last_logs

    def on_epoch_started(self):
        self._epoch_logs = defaultdict(list)

    def on_epoch_finished(self):
        epoch_logs = {f"{k}_epoch": np.mean(v) for k, v in self._epoch_logs.items()}
        # self.experiment.log(epoch_logs)
        return epoch_logs

    def close(self):
        pass
        # self.experiment.save()
        # self.experiment.close()