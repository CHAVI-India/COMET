import pydicom
from pydicom.errors import InvalidDicomError

from dcmrtstruct2nii.adapters.input.abstractinputadapter import AbstractInputAdapter
from dcmrtstruct2nii.exceptions import InvalidFileFormatException


class PatchedRtStructInputAdapter(AbstractInputAdapter):
    """Patched version of dcmrtstruct2nii's RtStructInputAdapter.

    Uses pydicom.dcmread instead of the deprecated pydicom.read_file.
    """

    def ingest(self, input_file, skip_contours=False):  # noqa: C901
        try:
            rt_struct_image = pydicom.dcmread(input_file)

            if not hasattr(rt_struct_image, 'StructureSetROISequence'):
                raise InvalidDicomError()

        except (IsADirectoryError, InvalidDicomError):
            raise InvalidFileFormatException('File {} is not an rt-struct dicom'.format(input_file))

        contours = []

        metadata_mappings = {}
        for contour_metadata in rt_struct_image.StructureSetROISequence:
            metadata_mappings[contour_metadata.ROINumber] = contour_metadata

        for contour_sequence in rt_struct_image.ROIContourSequence:
            contour_data = {}

            metadata = metadata_mappings[contour_sequence.ReferencedROINumber]

            if hasattr(metadata, 'ROIName'):
                contour_data['name'] = metadata.ROIName

            if hasattr(metadata, 'ROINumber'):
                contour_data['roi_number'] = metadata.ROINumber

            if hasattr(metadata, 'ReferencedFrameOfReferenceUID'):
                contour_data['referenced_frame'] = metadata.ReferencedFrameOfReferenceUID

            if hasattr(contour_sequence, 'ROIDisplayColor') and len(contour_sequence.ROIDisplayColor) > 0:
                contour_data['display_color'] = contour_sequence.ROIDisplayColor

            if not skip_contours and hasattr(contour_sequence, 'ContourSequence') and len(contour_sequence.ContourSequence) > 0:
                contour_data['sequence'] = []
                for contour in contour_sequence.ContourSequence:
                    contour_data['sequence'].append({
                        'type': (contour.ContourGeometricType if hasattr(contour, 'ContourGeometricType') else 'unknown'),
                        'points': {
                            'x': ([contour.ContourData[index] for index in range(0, len(contour.ContourData), 3)] if hasattr(contour, 'ContourData') else None),  # noqa: E501
                            'y': ([contour.ContourData[index + 1] for index in range(0, len(contour.ContourData), 3)] if hasattr(contour, 'ContourData') else None),  # noqa: E501
                            'z': ([contour.ContourData[index + 2] for index in range(0, len(contour.ContourData), 3)] if hasattr(contour, 'ContourData') else None)  # noqa: E501
                        }
                    })

            if contour_data:
                contours.append(contour_data)

        return contours
