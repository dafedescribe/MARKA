export const visibleLibraryScans = (scans = []) =>
  scans.filter((scan) => Boolean(scan.graded_image_path));

export const storedImageCount = (scans = []) =>
  scans.reduce(
    (count, scan) => count
      + (scan.image_path ? 1 : 0)
      + (scan.graded_image_path ? 1 : 0),
    0,
  );
