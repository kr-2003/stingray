import os
import copy
import tempfile

import numpy as np
import pytest
from astropy.io import fits

from stingray.crossspectrum import AveragedCrossspectrum
from stingray.events import EventList
from stingray.largememory import createChunkedSpectra, saveData, retrieveData
from stingray.lightcurve import Lightcurve
from stingray.powerspectrum import AveragedPowerspectrum

HAS_ZARR = False
try:
    import zarr

    HAS_ZARR = True
    from numcodecs import Blosc
except ImportError:
    pass

curdir = os.path.abspath(os.path.dirname(__file__))
datadir = os.path.join(curdir, 'data')


class TestSaveSpec(object):
    @classmethod
    def setup_class(cls):
        time = np.arange(0, 1e7)
        counts = np.random.poisson(10, time.size)
        cls.lc = Lightcurve(time, counts, skip_checks=True)

        evtimes = np.sort(np.random.uniform(0, 1e7, 10**7))
        cls.ev = EventList(time=evtimes)

        cls.file = tempfile.mkdtemp()

    @pytest.mark.skipif('not HAS_ZARR')
    def test_save_wrong_data(self):
        with pytest.raises(ValueError) as excinfo:
            saveData("A string", 'bububu')
        assert 'Invalid data: A string (str)' in str(excinfo.value)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_save_lc(self):
        test_lc = copy.deepcopy(self.lc)
        # Make sure counts_err exists
        _ = test_lc.counts_err

        print(self.file)
        saveData(test_lc, self.file)

        main = os.path.join(self.file, 'main_data')
        meta = os.path.join(self.file, 'meta_data')

        errors = []

        if (len([f for f in os.listdir(main) if not f.startswith('.')]) or len(
            [f for f in os.listdir(meta) if not f.startswith('.')])) == 0:
            errors.append("Lightcurve is not saved or does not exist")
        else:
            times = zarr.open_array(store=main, mode='r', path='times')[...]
            counts = zarr.open_array(store=main, mode='r', path='counts')[...]
            count_err = \
                zarr.open_array(store=main, mode='r', path='count_err')[...]
            gti = zarr.open_array(store=main, mode='r', path='gti')[...]
            gti = gti.reshape((gti.size // 2, 2))

            dt = zarr.open_array(store=meta, mode='r', path='dt')[...]
            mjdref = zarr.open_array(store=meta, mode='r', path='mjdref')[...]
            err_dist = \
                zarr.open_array(store=meta, mode='r', path='err_dist')[...]

            if not np.array_equal(test_lc.time, times):
                errors.append("lc.time is not saved precisely")
            if not np.array_equal(test_lc.counts, counts):
                errors.append("lc.counts is not saved precisely")
            if not np.array_equal(test_lc.counts_err, count_err):
                errors.append("lc.counts_err is not saved precisely")
            if not np.array_equal(test_lc.gti, gti):
                errors.append("lc.gti is not saved precisely")
            if not (test_lc.dt == dt):
                errors.append("lc.dt is not saved precisely")
            if not (test_lc.mjdref == mjdref):
                errors.append("lc.mjdref is not saved precisely")
            if not (test_lc.err_dist == err_dist):
                errors.append("lc.err_dist is not saved precisely")

        assert not errors, "Errors encountered:\n{}".format('\n'.join(errors))

    @pytest.mark.skipif('not HAS_ZARR')
    def test_save_ev(self):
        saveData(self.ev, self.file)

        main = os.path.join(self.file, 'main_data')
        meta = os.path.join(self.file, 'meta_data')

        errors = []

        if (len([f for f in os.listdir(main) if not f.startswith('.')]) or len(
            [f for f in os.listdir(meta) if not f.startswith('.')])) == 0:
            errors.append("EventList is not saved or does not exist")

        else:
            try:
                times = zarr.open_array(store=main, mode='r', path='times')
                if not np.array_equal(self.ev.time, times[...]):
                    errors.append("ev.time is not saved precisely")
            except ValueError:
                pass

            try:
                energy = zarr.open_array(store=main, mode='r', path='energy')
                if not np.array_equal(self.ev.energy, energy[...]):
                    errors.append("ev.energy is not saved precisely")
            except ValueError:
                pass

            try:
                pi_channel = zarr.open_array(store=main,
                                            mode='r',
                                            path='pi_channel')
                if not np.array_equal(self.ev.pi, pi_channel[...]):
                    errors.append("ev.pi is not saved precisely")
            except ValueError:
                pass

            try:
                gti = zarr.open_array(store=main, mode='r', path='gti')
                if not np.array_equal(self.ev.gti, gti[...]):
                    errors.append("ev.gti is not saved precisely")
            except ValueError:
                pass

            try:
                dt = zarr.open_array(store=meta, mode='r', path='dt')
                if self.ev.dt == dt[...]:
                    errors.append("ev.dt is not saved precisely")
            except ValueError:
                pass

            try:
                ncounts = zarr.open_array(store=meta, mode='r', path='ncounts')
                if self.ev.ncounts == ncounts[...]:
                    errors.append("ev.ncounts is not saved precisely")
            except ValueError:
                pass

            try:
                mjdref = zarr.open_array(store=meta, mode='r', path='mjdref')
                if self.ev.mjdref == mjdref[...]:
                    errors.append("ev.mjdref is not saved precisely")
            except ValueError:
                pass

            try:
                notes = zarr.open_array(store=meta, mode='r', path='notes')
                if self.ev.notes == notes[...]:
                    errors.append("ev.notes is not saved precisely")
            except ValueError:
                pass

        assert not errors, "Errors encountered:\n{}".format('\n'.join(errors))


    @pytest.mark.skipif('not HAS_ZARR')
    def test_save_fits_data(self):
        fname = os.path.join(datadir, 'monol_testA.evt')
        saveData(fname, self.file)

        with fits.open(fname) as fits_data:
            time_def = fits_data[1].data['TIME']
            try:
                pi_channel_def = fits_data[1].data['PI']
            except KeyError:
                pi_channel_def = fits_data[1].data['PHA']
            gti_def = fits_data[2].data

            tstart_def = fits_data[1].header['TSTART']
            tstop_def = fits_data[1].header['TSTOP']
            mjdref_def = fits_data[1].header['MJDREFI'] + fits_data[1].header[
                'MJDREFF']

        main = os.path.join(self.file, 'main_data')
        meta = os.path.join(self.file, 'meta_data')

        errors = []

        if (len([f for f in os.listdir(main) if not f.startswith('.')]) or len(
            [f for f in os.listdir(meta) if not f.startswith('.')])) == 0:
            errors.append("EventList is not saved or does not exist")
        else:
            try:
                times = zarr.open_array(store=main, mode='r', path='times')
                if not np.array_equal(time_def, times[...]):
                    errors.append(
                        "fits.events.data.time is not saved precisely")
            except ValueError:
                pass

            try:
                pi_channel = zarr.open_array(store=main,
                                             mode='r',
                                             path='times')
                if not np.array_equal(pi_channel_def, pi_channel[...]):
                    errors.append(
                        "fits.events.data.pi/fits.events.data.pha is not saved precisely"
                    )
            except ValueError:
                pass

            try:
                gti = zarr.open_array(store=main, mode='r', path='gti')
                if not np.array_equal(gti_def, gti[...]):
                    errors.append("fits.gti.data is not saved precisely")
            except ValueError:
                pass

            try:
                tstart = zarr.open_array(store=meta, mode='r', path='tstart')
                if not (tstart == tstart_def):
                    errors.append(
                        "fits.events.header.tstart is not saved precisely")
            except ValueError:
                pass

            try:
                tstop = zarr.open_array(store=meta, mode='r', path='tstop')
                if not (tstop == tstop_def):
                    errors.append(
                        "fits.events.header.tstop is not saved precisely")
            except ValueError:
                pass

            try:
                mjdref = zarr.open_array(store=meta, mode='r', path='tstart')
                if not (mjdref == mjdref_def):
                    errors.append(
                        "fits.events.header.mjdref is not saved precisely")
            except ValueError:
                pass

        assert not errors, "Errors encountered:\n{}".format('\n'.join(errors))


class TestRetrieveSpec(object):
    @classmethod
    def setup_class(cls):
        time = np.arange(0, 1e7)
        counts = np.random.poisson(10, time.size)
        cls.lc = Lightcurve(time, counts, skip_checks=True)

        evtimes = np.sort(np.random.uniform(0, 1e7, 10**7))
        cls.ev = EventList(time=evtimes)

        file = tempfile.mkdtemp()
        cls.path, cls.dir = os.path.split(file)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_wrong_data(self):
        saveData(self.lc, os.path.join(self.path, self.dir))
        with pytest.raises(ValueError) as excinfo:
            retrieveData("A string", self.dir, self.path)
        assert 'Invalid data: A string (str)' in str(excinfo.value)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_lc_data(self):
        saveData(self.lc, os.path.join(self.path, self.dir))

        lc = retrieveData(data_type='Lightcurve',
                          dir_name=self.dir,
                          path=self.path)

        assert lc.__eq__(self.lc) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_ev_data(self):
        saveData(self.ev, os.path.join(self.path, self.dir))

        ev = retrieveData(data_type='EventList',
                          dir_name=self.dir,
                          path=self.path)

        lc_main = self.ev.to_lc(dt=1.0)
        lc_other = ev.to_lc(dt=1.0)

        assert lc_main.__eq__(lc_other) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_fits_data(self):
        fname = os.path.join(datadir, 'monol_testA.evt')
        saveData(fname, os.path.join(self.path, self.dir))

        ev = retrieveData(data_type='FITS',
                          dir_name=self.dir,
                          path=self.path)

        lc_main = self.ev.to_lc(dt=1.0)
        lc_other = ev.to_lc(dt=1.0)

        assert lc_main.__eq__(lc_other) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_lc_chunk_data(self):
        saveData(self.lc, os.path.join(self.path, self.dir))

        lc = retrieveData(data_type='Lightcurve',
                          dir_name=self.dir,
                          path=self.path,
                          chunk_data=True,
                          chunk_size=10**5,
                          offset=0,
                          raw=False)

        trunc_lc = self.lc.truncate(stop=10**5)

        assert lc.__eq__(trunc_lc) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_ev_chunk_data(self):
        saveData(self.ev, os.path.join(self.path, self.dir))

        ev = retrieveData(data_type='EventList',
                          dir_name=self.dir,
                          path=self.path,
                          chunk_data=True,
                          chunk_size=10**5,
                          offset=0,
                          raw=False)

        lc_main = self.ev.to_lc(dt=1.0)
        lc_main = lc_main.truncate(stop=10**5)

        lc_other = ev.to_lc(dt=1.0)

        assert lc_main.__eq__(lc_other) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_lc_offset_data(self):
        saveData(self.lc, os.path.join(self.path, self.dir))

        lc = retrieveData(data_type='Lightcurve',
                          dir_name=self.dir,
                          path=self.path,
                          chunk_data=True,
                          chunk_size=10**5,
                          offset=10**2,
                          raw=False)

        trunc_lc = self.lc.truncate(start=10**2, stop=10**5)

        assert lc.__eq__(trunc_lc) is True

    @pytest.mark.skipif('not HAS_ZARR')
    def test_retrieve_ev_offset_data(self):
        saveData(self.ev, os.path.join(self.path, self.dir))

        ev = retrieveData(data_type='EventList',
                          dir_name=self.dir,
                          path=self.path,
                          chunk_data=True,
                          chunk_size=10**5,
                          offset=10**2,
                          raw=False)

        lc_main = self.ev.to_lc(dt=1.0)
        lc_main = lc_main.truncate(start=10**2, stop=10**5)

        lc_other = ev.to_lc(dt=1.0)

        assert lc_main.__eq__(lc_other) is True


class TestChunkPS(object):
    @classmethod
    def setup_class(cls):
        time = np.arange(2**24)
        counts1 = np.random.poisson(10, time.size)
        cls.lc1 = Lightcurve(time, counts1, skip_checks=True,
                             gti=[[0, 2**24]])
        cls.file1 = tempfile.mkdtemp()

        counts2 = np.random.poisson(10, time.size)
        cls.lc2 = Lightcurve(time, counts2, skip_checks=True,
                             gti=[[0, 2**24]])
        cls.file2 = tempfile.mkdtemp()

        saveData(cls.lc1, cls.file1)
        saveData(cls.lc2, cls.file2)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_invalid_data_to_pds(self):
        with pytest.raises(ValueError) as excinfo:
            AveragedPowerspectrum("sdfasfsa", segment_size=2048,
                                  large_data=True)
        assert 'Invalid input data type: str' in str(excinfo.value)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_invalid_data_to_cpds(self):
        with pytest.raises(ValueError) as excinfo:
            AveragedCrossspectrum("sdfasfsa", "sdfasfsa", segment_size=2048,
                                  large_data=True)
        assert 'Invalid input data type: str' in str(excinfo.value)

    @pytest.mark.skipif('not HAS_ZARR')
    def test_calc_pds(self):
        ps_normal = AveragedPowerspectrum(self.lc1, segment_size=2048)
        ps_large = AveragedPowerspectrum(self.lc1, segment_size=2048,
                                         large_data=True)

        for attr in [
                'freq', 'power', 'power_err', 'unnorm_power', 'df', 'm', 'n',
                'nphots', 'gti', 'norm', 'dt', 'power_type', 'type'
        ]:
            assert np.allclose(getattr(ps_normal, attr),
                               getattr(ps_large, attr))

    @pytest.mark.skipif('not HAS_ZARR')
    def test_calc_cpds(self):
        cs_normal = AveragedCrossspectrum(
            self.lc1, self.lc2, segment_size=2048)
        cs_large = AveragedCrossspectrum(
            self.lc1,  self.lc2, segment_size=2048, large_data=True)

        for attr in [
                'freq', 'power', 'power_err', 'unnorm_power', 'df', 'm', 'n',
                'nphots1', 'nphots2', 'gti', 'pds1.power', 'pds2.power',
                'norm', 'dt', 'power_type', 'type'
        ]:
            assert np.allclose(getattr(cs_normal, attr),
                               getattr(cs_large, attr))
