import nibabel as nib
import sys
import tempfile, os
sys.path.append('/home/grg/git/bbrc-validator/')
from bbrc.validation.utils import __is_valid_scan__
import numpy as np
import os.path as op
from matplotlib import pyplot as plt
from tqdm import tqdm
import pyxnat
import logging as log

def download_resources(config_fp, experiment_id, resource_name, wd):
    x = pyxnat.Interface(config=config_fp)


    t2_lut_names = ['T2_ALFA1']
    t2_scans = []
    e = x.select.experiment(experiment_id)
    scans = x.array.mrscans(experiment_id=experiment_id,\
            columns=['xnat:mrScanData/quality',
                     'xnat:mrScanData/type',
                     'xsiType']).data
    for s in scans:
        scan = e.scan(s['xnat:mrscandata/id'])

        if scan.attrs.get('type') in t2_lut_names and \
            __is_valid_scan__(x, s):
                t2_scans.append(scan.id())
    assert(len(t2_lut_names) == 1)

    filepaths = []
    t2_t1space = list(e.resource('ANTS').files('*%s*T1space.nii.gz'%t2_scans[0]))[0]
    fp1 = op.join(wd, '%s_T2_T1space.nii.gz'%experiment_id)
    filepaths.append(fp1)
    t2_t1space.get(fp1)

    r = e.resource(resource_name)
    for each in ['c1', 'c2', 'c3']:
        c = list(r.files('%s*.nii.gz'%each))[0]
        fp = op.join(wd, '%s_%s.nii.gz'%(experiment_id, each))
        c.get(fp)
        filepaths.append(fp)
    return filepaths


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def snap_slices(slices, axis, row_size, figsize, func, pbar=None):

    paths = []
    bb = {}

    for a, chunk in enumerate(chunks(slices, row_size)):
        _, path = tempfile.mkstemp(prefix='%s%s_'%(axis, a), suffix='.jpg')
        paths.append(path)
        bb[a] = []

        fig = plt.figure(dpi=300, figsize=figsize)

        for i, slice_index in enumerate(chunk):
            ax = fig.add_subplot(1, len(chunk), i+1, label='slice_%s'%slice_index)
            test = np.flip(np.swapaxes(np.abs(func(slice_index)), 0, 1), 0)
            xs, ys, zs = np.where(test!=0)
            bb[a].append((xs, ys, zs))

            if len(xs) == 0: continue
            test = test[min(xs):max(xs) + 1, min(ys):max(ys) + 1, :]

            ax.imshow((test * 255).astype(np.uint8), interpolation='none', )
            ax.axis('off')

            ax.text(0, 0, '%i' %slice_index,
                {'color': 'w', 'fontsize': 10}, va="bottom", ha="left")


            if not pbar is None:
                pbar.update(1)

        fig.savefig(path, facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                transparent=True,
                pad_inches=0)
    return paths, bb




def snap_slices_orig(slices, axis, row_size, figsize, func, bb, pbar=None):

    paths = []

    for a, chunk in enumerate(chunks(slices, row_size)):
        _, path = tempfile.mkstemp(prefix='%s%s_'%(axis, a), suffix='.jpg')
        paths.append(path)

        fig = plt.figure(dpi=300, figsize=figsize)

        for i, slice_index in enumerate(chunk):
            ax = fig.add_subplot(1, len(chunk), i+1, label='slice_%s'%slice_index)
            test = np.flip(np.swapaxes(np.abs(func(slice_index)), 0, 1), 0)
            xs, ys, zs = bb[a][i]

            if len(xs) == 0: continue
            test = test[min(xs):max(xs) + 1, min(ys):max(ys) + 1]

            ax.imshow(test, interpolation='none', cmap='gray')
            ax.axis('off')

            ax.text(0, 0, '%i' %slice_index,
                {'color': 'w', 'fontsize': 10}, va="bottom", ha="left")

            if not pbar is None:
                pbar.update(1)

        fig.savefig(path, facecolor=fig.get_facecolor(),
                bbox_inches='tight',
                transparent=True,
                pad_inches=0)
    return paths





def snap(filepaths, axes=['A', 'S', 'C'], orig=True):

    c = nib.load(filepaths[1]).dataobj.shape

    stack = [np.asarray(nib.load(e).dataobj) for e in filepaths[1:]]
    while len(stack) < 3:
        stack.append(np.zeros(c))

    data = np.stack(stack, axis=-1)
    if orig:
        orig_data = np.asarray(nib.load(filepaths[0]).dataobj)

    plt.rcParams['figure.facecolor'] = 'black'
    plt.rcParams.update({'figure.max_open_warning': 0})

    paths = {}
    paths_orig = {}
    slices = {'A': list(range(100, data.shape[2] - 60, 3)),
        'C': list(range(50, data.shape[1] - 70, 3)),
        'S': list(range(90, data.shape[0] - 90, 1))}

    lambdas = {'A': lambda x: data[:,:,x,:],
               'C': lambda x: data[:,x,:,:],
               'S': lambda x: data[x,:,:,:]}

    lambdas_orig = {'A': lambda x: orig_data[:,:,x],
               'C': lambda x: orig_data[:,x,:],
               'S': lambda x: orig_data[x,:,:]}

    row_sizes = {'A': 9, 'C': 9, 'S':6}
    fig_sizes = {'A': 37, 'C': 40, 'S':18}

    n_slices = sum([len(slices[e]) for e in axes])
    if orig:
        n_slices = 2 * n_slices

    pbar = tqdm(total=n_slices, leave=False)
    for each in axes:
        path, bb = snap_slices(slices[each], axis=each, row_size=row_sizes[each],
            figsize=(fig_sizes[each], 3), func=lambdas[each], pbar=pbar)
        paths[each] = path

        if orig:
            path = snap_slices_orig(slices[each], axis=each, row_size=row_sizes[each],
                figsize=(fig_sizes[each], 3), func=lambdas_orig[each], bb=bb,
                pbar=pbar)
            paths_orig[each] = path

    pbar.update(n_slices)
    pbar.close()
    return paths, paths_orig




def snap_files(filepaths, axes, orig, opacity, orig_fp):

    # FIXME: be careful if a file contains .gif or .jpg elsewhere

    width = 2000
    fp = orig_fp.replace('.gif', '.jpg')
    # Creating snapshots (along given axes and original if needed)
    log.info('* Creating snapshots...')
    paths, paths_orig = snap(filepaths, axes=axes, orig=orig)

    montage_cmd = 'montage -resize %sx -tile 1 -background black -geometry +0+0 %s %s'%(width, '%s', '%s')
    # Compiling images into a single one (one per axis)
    for each in axes:
        cmd = montage_cmd%(' '.join(paths[each]), fp.replace('.jpg', '_%s.jpg'%each))
        log.debug(cmd)
        os.system(cmd)
        for e in paths[each]:
            os.unlink(e) # Delete individual snapshots

    # Create one image with the selected axes
    cmd = montage_cmd%(' '.join([fp.replace('.jpg', '_%s.jpg'%each) for each in axes]), fp)
    log.debug(cmd)
    os.system(cmd)
    log.info('Saved in %s'%fp)


    if orig:
        # Repeat the process (montage) with the "raw" snapshots
        for each in axes:
            cmd = montage_cmd%(' '.join(paths_orig[each]), fp.replace('.jpg', '_orig_%s.jpg'%each))
            log.debug(cmd)
            os.system(cmd)
            for e in paths_orig[each]:
                os.unlink(e)

        # Create one image with the selected axes
        cmd = montage_cmd%(' '.join([fp.replace('.jpg', '_orig_%s.jpg'%each) for each in axes]),
                fp.replace('.jpg', '_orig.jpg'))
        log.debug(cmd)
        os.system(cmd)
        log.info('Saved in %s'%fp.replace('.jpg', '_orig.jpg'))


    # At this point there should be two images max. (segmentation and raw image)
    composite_cmd = 'composite -dissolve %s -gravity Center %s %s -alpha Set %s'

    if orig:
        if orig_fp.endswith('.gif'): # will generate a .gif

            # Fading from raw data to segmentation
            l = list(range(0, opacity, int(opacity/10.0)))
            pbar = tqdm(total=2*len(l), leave=False)
            for i, opac in enumerate(l):
                cmd = composite_cmd %(opac, fp, fp.replace('.jpg', '_orig.jpg'),
                        fp.replace('.jpg', '_fusion_%03d.jpg'%i))
                log.debug(cmd)
                os.system(cmd)
                pbar.update(1)

            # From segmentation to raw data
            for i, opac in enumerate(l):
                cmd = composite_cmd %(opacity - opac, fp, fp.replace('.jpg', '_orig.jpg'),
                        fp.replace('.jpg', '_fusion_%03d.jpg'%(len(l)+i)))
                log.debug(cmd)
                os.system(cmd)
                pbar.update(1)

            pbar.update(2*len(l))
            pbar.close()

            # Collect frames and create gif
            filepaths = []
            for i, opac in enumerate(range(0, 2 * opacity, int(opacity/10.0))):
                filepaths.append(fp.replace('.jpg', '_fusion_%03d.jpg'%i))

            cmd = 'convert -delay 0 -loop 0 %s %s'\
                %(' '.join(filepaths), fp.replace('.jpg', '.gif'))
            log.debug(cmd)
            os.system(cmd)
            log.info('Saved in %s'%fp.replace('.jpg', '.gif'))

            #Removing fusions (jpeg files)
            for each in filepaths:
                os.unlink(each)


        else:

            # Blends the two images (segmentation and original) into a composite one
            cmd = composite_cmd %(opacity, fp, fp.replace('.jpg', '_orig.jpg'),
                    fp.replace('.jpg', '_fusion.jpg'))
            log.debug(cmd)
            os.system(cmd)
            log.info('Saved in %s'%fp.replace('.jpg', '_fusion.jpg'))









if __name__ == '__main__':
    experiment_id = 'BBRCDEV_E02849'
    fp = '/tmp/fusion.jpg'
    resource_name = 'SPM12_SEGMENT_T2T1_COREG'
    config_fp = '/home/grg/.xnat_goperto_ci.cfg'
    axes = 'S'
    opacity = 100
    orig = True
    wd = tempfile.gettempdir()

    # Downloading resources
    log.info('* Downloading resources...')
    filepaths = download_resources(config_fp, experiment_id, resource_name, wd)

    snap_files(filepaths, axes, orig, opacity, fp)
