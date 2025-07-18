# Coded by Jonas Schenker
# Code for CellDistinction.ipynb

import numpy as np
import matplotlib.pyplot as plt
import os # To save images
from matplotlib import colors # To convert image models

from Functions.FinalKMeans import init_centroids
from Functions.FinalKMeans import assign_to_centroids
from Functions.FinalKMeans import update_centroids
from Functions.FinalKMeans import save_image
from Functions.FinalKMeans import save_image_universal

def preprocess_gray_with_coords(data, intensity_weight=2, mask=None):
    """
    Creates feature vectors from grayscale intensity and (x, y) coordinates.
    Optionally: mask = only for foreground (e.g., cells).
    - data: 2D array (grayscale image)
    - intensity_weight: weight for the intensity in the feature vector
    - mask: optional mask to exclude background pixels (e.g., cells)
    """
    h, w = data.shape
    X, Y = np.meshgrid(np.arange(w), np.arange(h))
    # Normalisiere Koordinaten und Intensität
    X = X / w
    Y = Y / h 
    #I = data / data.max() # Not necessary, as data is already normalized in kmeans_with_coords
    # intensity_weight should be 2 to adjust the influence of intensity in the feature vector, since if intensity_weight would be 1,
    # the influence of intensity wouldnt be equal to the influence of coordinates (coordinates weighted 2x since I,X,Y are stacked in the feature vector)
    I = data * intensity_weight 
    if mask is not None:
        features = np.stack([I[mask], X[mask], Y[mask]], axis=1)
    else:
        features = np.stack([I.ravel(), X.ravel(), Y.ravel()], axis=1)
    return features


#Segmentation with KMeans clustering using just created functions
def kmeans_with_coords(data, k, max_iters=100, tol=1e-4, init_method='kmeans++', intensity_weight=10, mask_usage = False, space='rgb'):
    """
    Complete K-Means workflow:
    1. init_centroids
    2. assign_to_centroids
    3. update_centroids
    4. Stop on convergence or max_iters
    Returns: centroids, labels, segmented_image
    - data: 2D array (grayscale image)
    - k: number of clusters
    - max_iters: maximum number of iterations
    - tol: tolerance for convergence, if the change in centroids is less than tol, stop
    - init_method: 'random' or 'kmeans++' for centroid initialization
    - intensity_weight: weighting of intensity in the feature vectors
    - mask_usage: if True, use a mask to exclude background pixels from segmentation
    - space: use 'rgb' due to dimensions of feature vector
    """

    #Normalize data
    data = np.copy(data.astype(float))
    data = (data - data.min()) / (data.max() - data.min())

    #Drop alpha channel if present
    #if data.ndim == 3 and data.shape[2] == 4:
     #   data = data[..., :3]
    #else:
     #   data = data

    # create mask to exclude background pixels from segmentation
    # step 1: create mask
    features = data.ravel().reshape(-1, 1)
    centroids = init_centroids(features, 2)
    for _ in range(max_iters):
        labels = assign_to_centroids(features, centroids)
        centroids = update_centroids(features, labels, 2)
        label_img = labels.reshape(data.shape)
        bg_cluster = np.argmin(centroids.flatten())
        mask = label_img != bg_cluster

    #Use segmented image (k=2) as mask for further processing 
    if mask_usage == True:
        img = preprocess_gray_with_coords(data, intensity_weight=intensity_weight, mask=mask)
    elif mask_usage == False:
        img = preprocess_gray_with_coords(data, intensity_weight=intensity_weight, mask=None)

    data_shape = data.shape
    centroids = init_centroids(img, k, method=init_method)
    for i in range(max_iters):
        labels = assign_to_centroids(img, centroids)
        new_centroids = update_centroids(img, labels, k)
        if np.linalg.norm(new_centroids - centroids) < tol:
            break
        centroids = new_centroids

        if mask_usage == True:
            segmented_image = reconstruct_colored_segmentation_mask(labels, mask, data_shape, k)
        elif mask_usage == False:
            segmented_image = reconstruct_colored_segmentation(labels, data_shape, k)
   
    return centroids, labels, segmented_image


def reconstruct_colored_segmentation_mask(labels, mask, shape, k):
    """
    Reconstructs a colored segmentation image with a black background.
    -labels: 1D array with cluster assignment for each pixel (e.g., shape (h*w,))
    -mask: boolean mask to exclude background pixels (e.g., cells)
    -shape: tuple with the target image shape (h, w, 3)
    -k: number of clusters
    """
    color_map = plt.cm.get_cmap('tab10', k)
    colors = color_map(np.arange(k))[:, :3]  # RGB-colors for clusters
    seg_img = np.zeros((shape[0], shape[1], 3))  # black as background/ intensity=0
    seg_img[mask] = colors[labels]
    return seg_img

def reconstruct_colored_segmentation(labels, shape, k):
    """
    Reconstructs a colored segmentation image without a mask.
    Each cluster is assigned its own color.
    -labels: 1D array with cluster assignment for each pixel (e.g., shape (h*w,))
    -shape: tuple with the target image shape (h, w, 3)
    -k: number of clusters
    """
    color_map = plt.cm.get_cmap('tab10', k)
    colors = color_map(np.arange(k))[:, :3]  # RGB-colors for clusters
    seg_img = colors[labels].reshape(shape[0], shape[1], 3)
    return seg_img


 # Function to identify the ideal number of clusters using the Elbow Method
def elbow_method_with_coords(data, max_k=10, max_iters=100, tol=1e-4, init_method='kmeans++', intensity_weight=2, mask_usage = False, space='rgb'):
    """
    Identifies the ideal number of clusters using the Elbow Method.

    Parameters:
    - data: 3D numpy array representing the image.
    - max_k: Maximum number of clusters to test.
    - max_iters: Maximum number of iterations for K-Means.
    - tol: Tolerance for convergence, if the change in centroids is less than tol, stop.
    - init_method: 'random' or 'kmeans++' for centroid initialization.
    - intensity_weight: weighting of intensity in the feature vectors
    - mask_usage: if True, use a mask to exclude background pixels from segmentation
    - space: use 'rgb' due to dimensions of feature vector

    Returns:
    - wcss: List of WCSS values for each k.
    """
    wcss = []

    #Drop alpha channel if present
    if data.ndim == 3 and data.shape[2] == 4:
        data = data[..., :3]
    else:
        data = data

# create mask to eclude background pixels from segmentation
    # step1: create also mask for reshaped_image --> needed for calculation of WCSS
    features = data.ravel().reshape(-1, 1)
    centroids = init_centroids(features, 2)
    for _ in range(max_iters):
        labels = assign_to_centroids(features, centroids)
        centroids = update_centroids(features, labels, 2)
        label_img = labels.reshape(data.shape)
        bg_cluster = np.argmin(centroids.flatten())
        mask = label_img != bg_cluster
    
    #select if mask should be used or not
    if mask_usage == True:
        img = preprocess_gray_with_coords(data, intensity_weight=intensity_weight, mask=mask)
    elif mask_usage == False:
        img = preprocess_gray_with_coords(data, intensity_weight=intensity_weight, mask=None)
        
    reshaped_image = img
    for k in range(1, max_k + 1):
        centroids, labels, _ = kmeans_with_coords(data, k, max_iters, tol, init_method, intensity_weight, mask_usage, space)
        # WCSS: Sum of squared distances of each point to its assigned centroid
        distances = np.sum((reshaped_image - centroids[labels]) ** 2)
        wcss.append(distances)
    return wcss