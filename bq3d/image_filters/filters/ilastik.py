"""
Inteface to Illastik for pixel classification

This module allows to integrate ilastik and its thresholding module into the *brainquant3d* pipeline.

To use ilastik within *brainquant3d* use the followng steps:

  * train a pixel classifier in ilastik

  * save the ilastik project under some file name <name>.ilp

  * pass the ilastik project file name to :meth:`PixelClassification`

"""

import os
import numpy as np
from pathlib import Path

from bq3d import io
from bq3d import config
from bq3d.image_filters import filter_manager
from bq3d.image_filters.filter import FilterBase

from bq3d._version import __version__
__author__     = 'Ricardo Azevedo, Jack Zeitoun'
__copyright__  = "Copyright 2019, Gandhi Lab"
__license__    = 'BY-NC-SA 4.0'
__version__    = __version__
__maintainer__ = 'Ricardo Azevedo'
__email__      = 'ricardo-re-azevedo@gmail.com'
__status__     = "Development"


class PixelClassification(FilterBase):
    """Run ilastik pixel classification in headless mode using a trained project file. Output will be a probabilty mask
    imdicating the probability that each voxel is a classified object.

    Attributes:
        input (array): Image to pass through filter, munt be memmapped.
        output (array): Filter result.
        project (str): ilastik .ilp project file. Must be creted using the ilastik pixel classification workflow.
        output_channel (int): ilastik pixel classifier will return a probabilty map for each label in the trainer.
        This chooses which one to keep
    """

    def __init__(self):
        self.ram = config.thread_ram_max
        self.processes = config.processes
        self.project = None #NOTE: Update this variable with a path to the ilastik filter
        self.output_channel = 0
        super().__init__(temp_dir = True)

    def _initialize_Ilastik(self):
        """Initialize all paths and binaries of ilastik
        """

        if config.ilastik_binary is None:
            raise RuntimeError(f'Cannot find Ilastix binary {config.ilastik_binary}, set Ilastik '
                               f'path in config filec accordingly!')

        config.ilastik_initialized = True
        self.log.verbose(f'Ilastik sucessfully initialized from path: {config.ilastik_path}')
        return True

    def _isValidInputFileName(self, filename):
        """Returns True if file can be read by Ilastik
        """

        validExtensions = ['bmp', 'exr', 'gif', 'jpg', 'jpeg', 'tif', 'tiff', 'ras',
                       'png', 'pbm', 'pgm', 'ppm', 'pnm', 'hdr', 'xv', 'npy']

        return io.fileExtension(filename) in validExtensions

    def _isValidOutputFileName(self, filename):
        """Returns True if Ilastik can output file type
        """

        validExtensions = ['bmp', 'gif', 'hdr', 'jpg', 'jpeg', 'pbm', 'pgm', 'png', 'pnm', 'ppm', 'ras', 'tif',
                               'tiff', 'xv', 'h5', 'npy']
        return io.fileExtension(filename) in validExtensions

    def _filename_to_input_arg(self, filename):
        """Converts file name to an Ilastik headless input arg
        """

        if not self._isValidInputFileName(filename):
            raise RuntimeError('Ilastik: file format not compatibel with Ilastik')

        return '"' + filename + '"'

    def _filename_to_output_arg(self, filename):
        """Converts file name to an Ilastik headless output arg
        """

        if not self._isValidOutputFileName(filename):
            raise RuntimeError('Ilastik: file format not compatibel with Ilastik output')

        else:  # single file
            valid_extensions = {'bmp': 'bmp', 'gif': 'gif', 'hdr': 'hrd',
                                'jpg': 'jpg', 'jpeg': 'jpeg', 'pbm': 'pbm',
                                'pgm': 'pgm', 'png': 'png', 'pnm': 'pnm', 'ppm': 'ppm',
                                'ras': 'ras', 'tif': 'tif', 'tiff': 'tiff', 'xv': 'xv',
                                'h5': 'hdf5', 'npy': 'numpy'}
            ext = valid_extensions[io.fileExtension(filename)]
            o = f'--output_format="{ext}" --output_filename_format="{filename}"'
            return o

    def run_headless(self, args):
        """Run Ilastik in headless mode with system RAM/prcesses config.
        """

        mem = self.ram * self.processes
        ram_mb = mem * 1000

        cmd = f'LAZYFLOW_THREADS={self.processes} ' \
              f'LAZYFLOW_TOTAL_RAM_MB={ram_mb} ' \
              f'{config.ilastik_binary} --headless {args}'
        self.log.info(f'running Ilastik command: {cmd}')
        res = os.system(cmd)

        if res != 0:
            raise RuntimeError('Ilastik command failed:' + cmd)
        return cmd

    def _generate_output(self):

        self._initialize_Ilastik()

        # create temp npy
        input_fn = str((self.temp_dir / Path(self.input.filename).stem).with_suffix('.npy'))
        io.writeData(input_fn, self.input)
        output_fn = str(self.temp_dir / 'out_prelim.npy')

        ilinp = self._filename_to_input_arg(input_fn)
        ilout = self._filename_to_output_arg(output_fn)
        cmd_args = f'--project="{self.project}" {ilout} {ilinp}'



        self.run_headless(cmd_args)

        output = io.readData(output_fn)
        output_chan = self.temp_dir / 'out.npy'
        # transpose to restore input dimensionality
        output_chan = io.writeData(output_chan,
                                    output[..., self.output_channel],
                                    returnMemmap=True)

        return output_chan

    def _validate_input(self):
        if not isinstance(self.input, np.memmap):
            raise RuntimeError('Ilastik input must be a memory mapped array')

filter_manager.add_filter(PixelClassification())
