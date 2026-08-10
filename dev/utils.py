from pycocotools.coco import COCO
from PIL import Image
import numpy as np
import tempfile
import zipfile
from radiomics import featureextractor
import SimpleITK as sitk
import cv2


def compute_GLCM(**kwargs):
      """
      Extract GLCM features from an image, constrained by a binary mask using SimpleITK.
      
      Args:
            image (SimpleITK.Image): The input image.
            mask (SimpleITK.Image): The binary mask.
      
      Returns:
            dict: A dictionary containing the GLCM feature values.
      """
      # Create a feature extractor
      extractor = featureextractor.RadiomicsFeatureExtractor()

      # Set the input image and mask
      extractor.settings['binWidth'] = 1
      extractor.settings['interpolator'] = 'sitkBSpline'
      extractor.settings['resampledPixelSpacing'] = None
      extractor.disableAllFeatures()
      extractor.enableFeatureClassByName('glcm')

      image = sitk.GetImageFromArray(kwargs.get('img'))
      mask = sitk.GetImageFromArray(kwargs.get('mask'))

      # Mask the input image
      image_masked = sitk.Mask(image, mask, 1)

      # Extract the GLCM features
      features = extractor.execute(image_masked, mask)

      # Return the GLCM feature values
      return {key: value for key, value in features.items()}

def compute_mean_echogen(**kwargs):
      img = kwargs.get('img')
      mask = kwargs.get('mask')
      masked_img = np.multiply(img, mask)
      return masked_img.sum() / kwargs.get('ann')['area']

FUNCTIONS = dict(
      mean_echogen = compute_mean_echogen,
      glcm = compute_GLCM
)

def extract_features(input_zip, funcs):
    
    """
    Perform annotation extraction and feature computations.
    @params
        input_zip (str)     : annotation zip file
        funcs (list or str) : functions to perform feature computations
                              use functions in `FUNCTIONS` above.
    
    E.g.
        extract_features("/Desktop/annot.zip", "mean_echogen") -> output mean echogen values
    """

    with zipfile.ZipFile(input_zip, 'r') as zip_file:
        extracted_data = []
        # Extract the annotation file
        with zip_file.open('annotations/instances_default.json') as f:
                annotation_data = f.read()
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write(annotation_data.decode('utf-8'))
                coco = COCO(tmp_file.name)
    
        

        for img_id in coco.getImgIds():
                    
                    # Load the image
                    img_info = coco.loadImgs(img_id)[0]
                    img_path = f"images/{img_info['file_name']}"
                    with zip_file.open(img_path) as f:
                        img = np.array(Image.open(f))
                        if len(img.shape) > 2:
                              img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    # Get the annotations for the current image
                    ann_ids = coco.getAnnIds(imgIds=img_id)
                    anns = coco.loadAnns(ann_ids)

                    if not anns: continue

                    for ann in anns:
                        # Get the category ID and the corresponding color code
                        cat_id = ann['category_id']
                        
                        # Draw the segmentation mask on the overlay image
                        mask = coco.annToMask(ann)
                        # mask = np.multiply(img, mask)
                        
                        cat_name = coco.cats[cat_id]['name']

                        current_data = dict(
                                structure = cat_name,
                                image = img_path,
                        )

                        if isinstance(funcs, str):
                              current_data.update({
                                    f"{funcs}" : FUNCTIONS[funcs](mask=mask, ann=ann, img=img)
                              })
                        
                        elif isinstance(funcs, list):
                              for func in funcs:
                                    current_data.update({
                                    f"{func}" : FUNCTIONS[func](mask=mask, ann=ann, img=img)
                              })
                        
                        else: continue

                        extracted_data.append(current_data)
    
        return extracted_data