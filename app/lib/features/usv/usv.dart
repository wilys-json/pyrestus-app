import 'dart:async';
import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const api = String.fromEnvironment('API_URL', defaultValue: '/api');

class Usv extends StatefulWidget {
  const Usv({super.key});

  @override
  State<Usv> createState() => _UsvState();
}

class _UsvState extends State<Usv> {
  final List<PlatformFile> files = [];

  String? folder;
  String? id;
  String format = 'png';
  String notice = '';
  bool busy = false;
  bool choosingFolder = false;
  Map<String, dynamic>? state;
  Timer? timer;

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  Future<void> pick() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['dcm', 'dicom', 'avi', 'mp4', 'mov', 'mkv'],
      withData: true,
    );

    if (result != null) {
      setState(() => files.addAll(result.files));
    }
  }

  Future<void> choose() async {
    setState(() => choosingFolder = true);

    try {
      final response = await http
          .post(Uri.parse('$api/output-directory/select'))
          .timeout(
            const Duration(seconds: 60),
            onTimeout: () => throw TimeoutException('Folder selector timed out'),
          );

      if (response.statusCode >= 400) {
        if (mounted) {
          setState(() {
            notice = 'Could not open the output-folder selector.';
          });
        }
        return;
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;

      if (mounted) {
        setState(() {
          folder = data['path'] as String?;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          notice =
              'Could not open the output-folder selector. '
              'Make sure the local app is running.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => choosingFolder = false);
      }
    }
  }

  Future<void> start() async {
    if (files.isEmpty || folder == null) {
      return;
    }

    setState(() => busy = true);

    try {
      final createResponse = await http.post(
        Uri.parse('$api/jobs'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'output_format': format}),
      );

      if (createResponse.statusCode >= 400) {
        throw Exception('Could not create a processing job.');
      }

      final job = jsonDecode(createResponse.body) as Map<String, dynamic>;
      final jobId = job['id'] as String;

      final uploadRequest = http.MultipartRequest(
        'POST',
        Uri.parse('$api/jobs/$jobId/files'),
      );

      for (final file in files) {
        if (file.bytes != null) {
          uploadRequest.files.add(
            http.MultipartFile.fromBytes(
              'files',
              file.bytes!,
              filename: file.name,
            ),
          );
        }
      }

      final uploadResponse = await uploadRequest.send();

      if (uploadResponse.statusCode >= 400) {
        throw Exception('Could not upload the selected files.');
      }

      final processResponse = await http.post(
        Uri.parse('$api/jobs/$jobId/process'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'output_directory': folder,
          'output_format': format,
        }),
      );

      if (processResponse.statusCode >= 400) {
        throw Exception('Could not begin processing.');
      }

      setState(() => id = jobId);

      timer?.cancel();
      timer = Timer.periodic(
        const Duration(seconds: 1),
        (_) => poll(),
      );

      await poll();
    } catch (_) {
      setState(() {
        notice =
            'Could not start processing. Please restart Pyrestus and try again.';
      });
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  Future<void> poll() async {
    if (id == null) {
      return;
    }

    try {
      final response = await http.get(Uri.parse('$api/jobs/$id'));

      if (response.statusCode >= 400) {
        return;
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;

      if (!mounted) {
        return;
      }

      setState(() => state = data);

      if (data['status'] == 'completed' || data['status'] == 'failed') {
        timer?.cancel();
      }
    } catch (_) {
      // Keep polling: a transient local connection failure should not
      // erase the user's job status.
    }
  }

  Future<void> openOutputFolder() async {
    if (id == null) {
      return;
    }

    await http.post(
      Uri.parse('$api/jobs/$id/open-output-directory'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isComplete = state?['status'] == 'completed';
    final hasFailed = state?['status'] == 'failed';

    return Scaffold(
      appBar: AppBar(title: const Text('Ultrasound Video Tools')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text(
                'Create image frames',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              const Text(
                'Add DICOM ultrasound files or standard video files. '
                'Results are saved to a folder you choose.',
              ),
              if (notice.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  notice,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
              const SizedBox(height: 20),
              _section(
                context,
                '1. Add files',
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    OutlinedButton.icon(
                      onPressed: busy ? null : pick,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Choose files'),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      files.isEmpty
                          ? 'No files selected.'
                          : '${files.length} file(s): '
                              '${files.map((file) => file.name).join(', ')}',
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'DICOM: .dcm, .dicom. Video: .avi, .mp4, .mov, .mkv.',
                      style: TextStyle(fontSize: 12),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              _section(
                context,
                '2. Select output folder',
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(folder ?? 'No output folder selected.'),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: busy || choosingFolder ? null : choose,
                      icon: choosingFolder
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.folder_open),
                      label: Text(
                        choosingFolder
                            ? 'Waiting for folder selection...'
                            : folder == null
                                ? 'Choose output folder'
                                : 'Change folder',
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              _section(
                context,
                '3. Output format',
                DropdownButton<String>(
                  isExpanded: true,
                  value: format,
                  items: const [
                    DropdownMenuItem(
                      value: 'png',
                      child: Text('PNG image frames (recommended)'),
                    ),
                    DropdownMenuItem(
                      value: 'jpg',
                      child: Text('JPG image frames'),
                    ),
                  ],
                  onChanged: busy
                      ? null
                      : (value) => setState(() => format = value!),
                ),
              ),
              const SizedBox(height: 20),
              if (state != null) _result(context, isComplete, hasFailed),
              if (!isComplete && !hasFailed)
                FilledButton.icon(
                  onPressed: busy || files.isEmpty || folder == null
                      ? null
                      : start,
                  icon: Icon(
                    busy ? Icons.hourglass_top : Icons.play_arrow,
                  ),
                  label: Text(
                    busy ? 'Preparing...' : 'Start processing',
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _section(BuildContext context, String title, Widget body) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 10),
            body,
          ],
        ),
      ),
    );
  }

  Widget _result(BuildContext context, bool complete, bool failed) {
    final job = state!;
    final completedFiles = job['files_completed'] ?? 0;
    final totalFiles = job['total_files'] ?? 0;

    return Card(
      color: complete
          ? Theme.of(context).colorScheme.primaryContainer
          : failed
              ? Theme.of(context).colorScheme.errorContainer
              : null,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              complete
                  ? 'Processing complete'
                  : failed
                      ? 'Processing needs attention'
                      : 'Processing',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              failed
                  ? '${job['message']}: ${job['error'] ?? ''}'
                  : job['message'] ?? '',
            ),
            if (!complete && !failed) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: totalFiles == 0 ? null : completedFiles / totalFiles,
              ),
            ],
            if (complete) ...[
              const SizedBox(height: 8),
              Text(
                '$completedFiles of $totalFiles files processed. '
                '${job['frames_created']} image frames were saved.',
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: openOutputFolder,
                icon: const Icon(Icons.folder_open),
                label: const Text('Open output folder'),
              ),
            ],
            const SizedBox(height: 4),
          ],
        ),
      ),
    );
  }
}