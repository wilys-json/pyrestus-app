import numpy as np
import matplotlib.pyplot as plt
import zipfile
import cv2
import tempfile
from pathlib import Path
from pycocotools.coco import COCO
from PIL import Image
from matplotlib import gridspec
import matplotlib.animation as animation
from dataclasses import dataclass
from . import utils
from .utils import *

@dataclass(init=False)
class SKIP:

    """
    Data object for Sequencing and Kinematic Instance Profiling.
    """
    input_zip = None
    config = None
    images = None
    _retr = dict(
        mask = "get_mask",
        coordinates = "get_coords"
    )
    _extr = dict(
        contour = "find_contour",
        anchoring_point = "get_anchoring_pt"
    )



    def __init__(self, input_zip, config):
        self.input_zip = input_zip
        self.config = config
        for attr, value in self.config.items():
            setattr(self, attr, value)
        self._get_annotated_imgs()
        self._get_annotations()
    
    def _get_annotated_imgs(self):
        """
        Visualize COCO annotations on the corresponding images and store the overlay images in a list.
        
        Parameters:
        zip_file_path (str): Path to the zip file containing the COCO annotations and images.
        
        Returns:
        list: List of overlay images.
        """
        # Open the zip file
        with zipfile.ZipFile(self.input_zip, 'r') as zip_file:
            # Extract the annotation file
            with zip_file.open('annotations/instances_default.json') as f:
                annotation_data = f.read()
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(annotation_data.decode('utf-8'))
                coco = COCO(tmp_file.name)
            
            # Get the category IDs and their corresponding color codes
            coco_colors = np.random.randint(0, 256, size=(len(coco.getCatIds()), 3))
            
            # List to store the overlay images
            overlay_images = []
            
            # Iterate over the images
            for img_id in coco.getImgIds():
                # Load the image
                img_info = coco.loadImgs(img_id)[0]
                img_path = f"images/{img_info['file_name']}"
                with zip_file.open(img_path) as f:
                    img = np.array(Image.open(f))
                
                # Create a copy of the image for the segmentation overlay
                overlay_img = img.copy()
                if len(overlay_img.shape) == 2:
                    overlay_img = cv2.cvtColor(overlay_img.copy(), cv2.COLOR_GRAY2BGR)
                
                # Get the annotations for the current image
                ann_ids = coco.getAnnIds(imgIds=img_id)
                anns = coco.loadAnns(ann_ids)

                if not anns: continue

                # Iterate over the annotations and overlay the segmentation masks
                masks = []
                for ann in anns:
                    # Get the category ID and the corresponding color code
                    cat_id = ann['category_id']
                    color = list(coco_colors[cat_id - 1])
                    mask_array = np.full(overlay_img.shape, color, dtype=np.uint8)
                    
                    # Draw the segmentation mask on the overlay image
                    mask = coco.annToMask(ann)
                    mask = np.multiply(mask_array, np.expand_dims(mask,-1))
                    masks.append(mask)
                mask_img = Image.fromarray(sum(masks)).convert('RGBA')
                overlay_img = Image.fromarray(overlay_img).convert('RGBA')
                overlay_img = Image.blend(overlay_img, mask_img, alpha=getattr(self, "alpha", .5))
                overlay_images.append(overlay_img)

        self.images = overlay_images
    
    def _get_annotations(self):

        with zipfile.ZipFile(self.input_zip, 'r') as zip_file:
            # Extract the annotation file
            with zip_file.open('annotations/instances_default.json') as f:
                annotation_data = f.read()
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(annotation_data.decode('utf-8'))
                coco = COCO(tmp_file.name)

                for annot in self.extraction_config:
                    structure_name = annot['structure']
                    retr_method = getattr(utils, self._retr[annot["extraction_object"]])
                    temp = [obj for seg in retr_method(tmp_file.name, structure_name) for id, obj in seg.items()]
                    extract = getattr(utils, self._extr[annot["extraction_method"]["func"]])
                    extract_args = annot["extraction_method"]["args"]
                    setattr(self, structure_name, [extract(obj, **extract_args) for obj in temp])
    
    def _prepare_viz(self):
        self.viz_fig = plt.figure()
        self.viz_fig.set_figheight(30)
        self.viz_fig.set_figwidth(30)

        n_viz = len(self.viz_config['structures'].keys())

        self.viz_specs = gridspec.GridSpec(ncols=1, nrows=n_viz+1,
                                        hspace=0.5, height_ratios=[1 for _ in range(n_viz)]+[n_viz+1])

        self.viz_axes = []

        for i in range(n_viz):
            ax = self.viz_fig.add_subplot(self.viz_specs[i])
            self.viz_axes.append(ax)

        self.ultrasound_viz = self.viz_fig.add_subplot(self.viz_specs[-1])
        self.ultrasound_viz.axis('off')

    def _animate(self, frame):
        
        # Clear the last frame
        for ax in self.viz_axes:
            ax.clear()
        self.ultrasound_viz.clear()

        for i, (structure, config) in enumerate(self.viz_config['structures'].items()):
            to_draw = []
            
            data = compute_kineseq(input=getattr(self,structure), **config['kineseq'])
            
            plot_info = config['plot']

            axis = self.viz_axes[i]
            axis.set_title(plot_info['title'])
            axis.set_ylabel(plot_info['unit'], fontsize=6)
            axis.set_xlabel('Time (s)')
            

            for line in plot_info['lines']:
                line_plot, = axis.plot(data[line['param']][:frame], label=line['label'])
                to_draw += [line_plot]

            max_disp = data['disp'].argmax()
            onset = data['onset']
            max_reached = data['max']
            offset = data['offset']
            
            if frame > max_disp:
                max_line = axis.axvline(x=max_disp, color='black', label='maximum displacement', linestyle='--')
                to_draw.append(max_line)

            if frame > onset:
                if frame < max_reached:
                    init = axis.axvspan(onset, frame, color='magenta', alpha=0.3, label='initiating period')
                    to_draw.append(init)
                elif frame >= max_reached:
                    init = axis.axvspan(onset, max_reached, color='magenta', alpha=0.3, label='initiating period')
                    to_draw.append(init)
                else: pass
            
            if frame > max_reached:
                if frame < offset:
                    sus = axis.axvspan(max_reached, frame, color='yellow', alpha=0.3, label='sustaining period')
                    to_draw.append(sus)
                elif frame >= offset:
                    sus = axis.axvspan(max_reached, offset, color='yellow', alpha=0.3, label='sustaining period')
                    to_draw.append(sus)
                else: pass
            
            axis.set_xticks(ticks=axis.get_xticks()[1:], labels=(self.frame_time * np.array(axis.get_xticks()[1:], dtype=np.float64)).round(2))
            axis.legend(handles=to_draw, loc='lower right', fontsize='xx-small')
        self.ultrasound_viz.imshow(self.images[frame])
        return to_draw
    
    def animate(self, output_pth=None):
        self._prepare_viz()
        self.ani = animation.FuncAnimation(self.viz_fig, self._animate, frames=len(self.images), interval=self.viz_config['interval'], blit=True)
        if output_pth:
            self.ani.save(output_pth)
