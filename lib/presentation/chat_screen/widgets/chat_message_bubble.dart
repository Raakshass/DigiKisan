import 'dart:typed_data';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:digikisan/core/app_export.dart';
import 'package:digikisan/services/image_service.dart';

/// A single chat message bubble.
/// Handles both user and bot messages with optional image attachment
/// and voice playback button for bot messages.
class ChatMessageBubble extends StatelessWidget {
  final Map<String, String> message;
  final bool isDiseaseConversation;
  final String? userName;
  final bool isPlayingResponse;
  final VoidCallback? onPlayVoice;

  const ChatMessageBubble({
    Key? key,
    required this.message,
    this.isDiseaseConversation = false,
    this.userName,
    this.isPlayingResponse = false,
    this.onPlayVoice,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isUser = message['sender'] == 'user';

    return Container(
      margin: EdgeInsets.only(bottom: 12.h),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            _buildBotAvatar(),
            SizedBox(width: 8.h),
          ],
          ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.78,
            ),
            child: _buildBubbleBody(isUser),
          ),
          if (isUser) ...[
            SizedBox(width: 8.h),
            _buildUserAvatar(),
          ],
        ],
      ),
    );
  }

  Widget _buildBotAvatar() {
    return CircleAvatar(
      radius: 16.h,
      backgroundColor: appTheme.colorFF065F,
      child: Icon(
        isDiseaseConversation ? Icons.healing : Icons.eco,
        color: appTheme.whiteCustom,
        size: 16,
      ),
    );
  }

  Widget _buildUserAvatar() {
    return CircleAvatar(
      radius: 16.h,
      backgroundColor: appTheme.colorFFF3F4,
      child: userName != null
          ? Text(
              userName!.substring(0, 1).toUpperCase(),
              style: TextStyle(
                color: appTheme.colorFF065F,
                fontSize: 12.fSize,
                fontWeight: FontWeight.bold,
              ),
            )
          : Icon(Icons.person, color: appTheme.colorFF065F, size: 16),
    );
  }

  Widget _buildBubbleBody(bool isUser) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 12.h, vertical: 8.h),
      decoration: BoxDecoration(
        color: isUser ? appTheme.colorFF065F : appTheme.whiteCustom,
        borderRadius: BorderRadius.circular(12.h),
        border: isUser
            ? null
            : Border.all(color: appTheme.colorFF10B9, width: 1.h),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (message['image_path'] != null) _buildImageAttachment(),
          _buildTextRow(isUser),
        ],
      ),
    );
  }

  Widget _buildImageAttachment() {
    return Container(
      margin: EdgeInsets.only(bottom: 8.h),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8.h),
        child: message['image_bytes'] != null
            ? Image.memory(
                base64Decode(message['image_bytes']!),
                width: 200.w,
                height: 150.h,
                fit: BoxFit.cover,
              )
            : FutureBuilder<Uint8List>(
                future: ImageService.getImageBytes(message['image_path']!),
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.done &&
                      snapshot.hasData &&
                      snapshot.data!.isNotEmpty) {
                    return Image.memory(
                      snapshot.data!,
                      width: 200.w,
                      height: 150.h,
                      fit: BoxFit.cover,
                    );
                  }
                  return Container(
                    width: 200.w,
                    height: 150.h,
                    decoration: BoxDecoration(
                      color: Colors.grey.shade200,
                      borderRadius: BorderRadius.circular(8.h),
                    ),
                    child: const Center(child: Icon(Icons.image_not_supported)),
                  );
                },
              ),
      ),
    );
  }

  Widget _buildTextRow(bool isUser) {
    return Row(
      children: [
        Expanded(
          child: Text(
            message['text'] ?? '',
            softWrap: true,
            textAlign: TextAlign.left,
            style: TextStyleHelper.instance.body14.copyWith(
              color: isUser ? appTheme.whiteCustom : appTheme.blackCustom,
            ),
          ),
        ),
        // Voice playback button for bot messages
        if (!isUser && message['text'] != null && onPlayVoice != null) ...[
          SizedBox(width: 8.h),
          GestureDetector(
            onTap: onPlayVoice,
            child: Container(
              padding: EdgeInsets.all(4.h),
              decoration: BoxDecoration(
                color: isPlayingResponse
                    ? appTheme.colorFF065F
                    : appTheme.colorFF065F.withAlpha(50),
                borderRadius: BorderRadius.circular(4.h),
              ),
              child: Icon(
                isPlayingResponse ? Icons.pause : Icons.volume_up,
                color: isPlayingResponse
                    ? appTheme.whiteCustom
                    : appTheme.colorFF065F,
                size: 12.h,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
