import 'dart:typed_data';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:mime/mime.dart';
import 'package:http_parser/http_parser.dart';
import 'dart:convert';

class ImageService {
  static final ImagePicker _picker = ImagePicker();
  static const String baseUrl = 'http://10.61.89.244:8000/api';

  // ✅ FIXED: Platform-agnostic image picker
  static Future<XFile?> pickImage({required bool fromCamera}) async {
    try {
      final XFile? image = await _picker.pickImage(
        source: fromCamera ? ImageSource.camera : ImageSource.gallery,
        maxWidth: 800,
        maxHeight: 600,
        imageQuality: 80,
      );
      
      if (image != null) {
        print('✅ Image picked: ${image.path}');
        return image;
      } else {
        print('❌ No image selected');
        return null;
      }
    } catch (e) {
      print('❌ Image picker error: $e');
      return null;
    }
  }

  // ✅ FIXED: Web-compatible image upload with proper MediaType handling
  static Future<Map<String, dynamic>> uploadForDiseaseDetection(XFile image) async {
    try {
      print('📤 Uploading image for disease detection...');
      
      // Get image bytes (works on both mobile and web)
      final Uint8List bytes = await image.readAsBytes();
      
      // Detect MIME type and split it properly
      final String mimeType = lookupMimeType(image.path) ?? 'image/jpeg';
      final List<String> mimeTypeData = mimeType.split('/');
      
      // Create multipart request
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/disease/predict'),
      );

      // ✅ FIXED: Create MediaType with separate type and subtype
      var multipartFile = http.MultipartFile.fromBytes(
        'file',                    // Field name expected by backend
        bytes,                     // Image bytes
        filename: image.name,      // Original filename
        contentType: MediaType(mimeTypeData[0], mimeTypeData[1]), // ✅ FIXED
      );

      request.files.add(multipartFile);

      // Send request
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      print('📡 Upload response status: ${response.statusCode}');
      print('📡 Upload response body: ${response.body}');

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Disease detection failed: ${response.statusCode}');
      }
    } catch (e) {
      print('❌ Upload error: $e');
      throw Exception('Upload error: $e');
    }
  }

  // ✅ Enhanced image source selection dialog
  static Future<XFile?> showImageSourceDialog(BuildContext context) async {
    XFile? selectedImage;
    
    await showModalBottomSheet(
      context: context,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (BuildContext context) {
        return SafeArea(
          child: Container(
            padding: EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Select Image Source',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    // Gallery option
                    GestureDetector(
                      onTap: () async {
                        selectedImage = await pickImage(fromCamera: false);
                        Navigator.of(context).pop();
                      },
                      child: Column(
                        children: [
                          Container(
                            padding: EdgeInsets.all(20),
                            decoration: BoxDecoration(
                              color: Colors.blue.shade50,
                              borderRadius: BorderRadius.circular(15),
                            ),
                            child: Icon(
                              Icons.photo_library,
                              size: 30,
                              color: Colors.blue,
                            ),
                          ),
                          SizedBox(height: 8),
                          Text('Gallery'),
                        ],
                      ),
                    ),
                    
                    // Camera option
                    GestureDetector(
                      onTap: () async {
                        selectedImage = await pickImage(fromCamera: true);
                        Navigator.of(context).pop();
                      },
                      child: Column(
                        children: [
                          Container(
                            padding: EdgeInsets.all(20),
                            decoration: BoxDecoration(
                              color: Colors.green.shade50,
                              borderRadius: BorderRadius.circular(15),
                            ),
                            child: Icon(
                              Icons.photo_camera,
                              size: 30,
                              color: Colors.green,
                            ),
                          ),
                          SizedBox(height: 8),
                          Text('Camera'),
                        ],
                      ),
                    ),
                  ],
                ),
                SizedBox(height: 20),
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: Text('Cancel'),
                ),
              ],
            ),
          ),
        );
      },
    );
    
    return selectedImage;
  }

  // ✅ FIXED: Get image bytes for web/mobile compatibility
  static Future<Uint8List> getImageBytes(String imagePath) async {
    try {
      if (imagePath.startsWith('blob:')) {
        // Web: Handle blob URLs
        final response = await http.get(Uri.parse(imagePath));
        return response.bodyBytes;
      } else {
        // Mobile: Handle file paths
        final file = File(imagePath);
        return await file.readAsBytes();
      }
    } catch (e) {
      print('❌ Error loading image bytes: $e');
      return Uint8List(0);
    }
  }

  // ✅ Validate image file
  static bool isValidImageFile(XFile file) {
    final String? mimeType = lookupMimeType(file.path);
    return mimeType != null && mimeType.startsWith('image/');
  }
}
