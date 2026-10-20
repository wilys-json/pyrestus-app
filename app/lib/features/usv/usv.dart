import 'dart:async';
import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const api = String.fromEnvironment('API_URL', defaultValue: '/api');

enum JobStatus { idle, running, completed, failed }

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
  bool polling = false;
  Map<String, dynamic>? state;
  Timer? timer;

  JobStatus get status => switch (state?['status']) {
        'completed' => JobStatus.completed,
        'failed' => JobStatus.failed,
        'processing' => JobStatus.running,
        _ => JobStatus.idle,
      };


  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  void _setNotice(String message) {
    if (mounted) setState(() => notice = message);
  }

  // ---------------------------------------------------------------- files

  Future<void> pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['dcm', 'dicom', 'avi', 'mp4', 'mov', 'mkv'],
      // Web has no file paths, so it needs bytes. Desktop streams from disk.
      withData: kIsWeb,
    );
    if (result == null || !mounted) return;

    setState(() {
      notice = '';
      for (final f in result.files) {
        final dup = files.any((e) =>
            e.name == f.name && e.size == f.size && e.path == f.path);
        if (!dup) files.add(f);
      }
    });
  }

  // --------------------------------------------------------------- folder

  Future<void> chooseFolder() async {
    if (choosingFolder) return;
    setState(() {
      choosingFolder = true;
      notice = '';
    });

    try {
      final path = kIsWeb ? await _chooseViaBackend() : await _chooseNative();
      if (path != null && path.isNotEmpty && mounted) {
        setState(() => folder = path);
      }
    } on TimeoutException {
      _setNotice('No folder was chosen. The dialog may be hidden behind '
          'another window; check your taskbar or dock.');
    } catch (e) {
      _setNotice('Could not open the folder selector ($e). '
          'Make sure the local app is running.');
    } finally {
      if (mounted) setState(() => choosingFolder = false);
    }
  }

  /// Desktop build: native OS dialog, shows system folders and external drives.
  Future<String?> _chooseNative() {
    return FilePicker.platform.getDirectoryPath(
      dialogTitle: 'Choose output folder',
      initialDirectory: folder,
      lockParentWindow: true,
    );
  }

  /// Web build: the backend opens the dialog. The user may take a while,
  /// so allow several minutes instead of 60 s.
  Future<String?> _chooseViaBackend() async {
    final res = await http
        .post(Uri.parse('$api/output-directory/select'))
        .timeout(const Duration(minutes: 5));

    if (res.statusCode == 409) {
      _setNotice('A folder dialog is already open. Check your taskbar or dock.');
      return null;
    }
    if (res.statusCode >= 400) {
      throw Exception(_detail(res.body, res.statusCode));
    }

    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return data['selected'] == true ? data['path'] as String? : null;
  }


  // ------------------------------------------------------------ processing

  Future<void> start() async {
    if (files.isEmpty || folder == null || busy) return;
    setState(() {
      busy = true;
      notice = '';
    });

    try {
      final createRes = await http.post(
        Uri.parse('$api/jobs'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'output_format': format}),
      );
      _check(createRes, 'create a processing job', createRes.body);
      final jobId =
          (jsonDecode(createRes.body) as Map<String, dynamic>)['id'] as String;

      final upload =
          http.MultipartRequest('POST', Uri.parse('$api/jobs/$jobId/files'));
      for (final f in files) {
        if (f.bytes != null) {
          upload.files.add(
              http.MultipartFile.fromBytes('files', f.bytes!, filename: f.name));
        } else if (f.path != null) {
          upload.files.add(await http.MultipartFile.fromPath('files', f.path!,
              filename: f.name));
        }
      }
      final uploadStreamed = await upload.send();
      final uploadRes = await http.Response.fromStream(uploadStreamed);
      _check(uploadRes, 'upload the selected files', uploadRes.body);

      // The backend reports skipped files, e.g. "Files ready (skipped: x.txt)"
      final uploaded = jsonDecode(uploadRes.body) as Map<String, dynamic>;
      final msg = uploaded['message'] as String? ?? '';
      if (msg.contains('skipped')) _setNotice(msg);

      final processRes = await http.post(
        Uri.parse('$api/jobs/$jobId/process'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'output_directory': folder, 'output_format': format}),
      );
      _check(processRes, 'begin processing', processRes.body);

      if (!mounted) return;
      setState(() => id = jobId);
      timer?.cancel();
      timer = Timer.periodic(const Duration(seconds: 1), (_) => poll());
      await poll();
    } catch (e) {
      _setNotice(e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _check(http.BaseResponse res, String what, [String body = '']) {
    if (res.statusCode >= 400) {
      throw Exception('Could not $what: ${_detail(body, res.statusCode)}');
    }
  }


    /// Extracts FastAPI's `detail` message (string or validation list).
  String _detail(String body, int code) {
    try {
      final d = (jsonDecode(body) as Map<String, dynamic>)['detail'];
      if (d is String) return d;
      if (d is List && d.isNotEmpty) {
        return (d.first as Map<String, dynamic>)['msg']?.toString() ?? 'HTTP $code';
      }
    } catch (_) {}
    return 'HTTP $code';
  }


  Future<void> poll() async {
    if (id == null || polling) return; // no overlapping requests
    polling = true;
    try {
      final res = await http.get(Uri.parse('$api/jobs/$id'));
      if (res.statusCode >= 400 || !mounted) return;
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      setState(() => state = data);
      if (status == JobStatus.completed || status == JobStatus.failed) {
        timer?.cancel();
      }
    } catch (_) {
      // Transient local failure: keep polling.
    } finally {
      polling = false;
    }
  }

  Future<void> openOutputFolder() async {
    if (id == null) return;
    try {
      await http.post(Uri.parse('$api/jobs/$id/open-output-directory'));
    } catch (e) {
      _setNotice('Could not open the output folder: $e');
    }
  }

  void reset() {
    timer?.cancel();
    setState(() {
      files.clear();
      id = null;
      state = null;
      notice = '';
    });
  }

  // ------------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final locked = busy || status == JobStatus.running;

    return Scaffold(
      appBar: AppBar(title: const Text('Ultrasound Video Tools')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Text('Create image frames', style: theme.textTheme.headlineSmall),
              const SizedBox(height: 6),
              Text(
                'Add DICOM ultrasound or video files. '
                'Frames are saved to a folder you choose.',
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
              if (notice.isNotEmpty) ...[
                const SizedBox(height: 16),
                _Banner(message: notice, onClose: () => setState(() => notice = '')),
              ],
              const SizedBox(height: 20),

              _Step(
                number: 1,
                title: 'Add files',
                done: files.isNotEmpty,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (files.isNotEmpty) ...[
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final f in files)
                            InputChip(
                              avatar: Icon(_iconFor(f.name), size: 18),
                              label: Text('${f.name}  ·  ${_size(f.size)}'),
                              onDeleted: locked
                                  ? null
                                  : () => setState(() => files.remove(f)),
                            ),
                        ],
                      ),
                      const SizedBox(height: 12),
                    ],
                    Row(
                      children: [
                        OutlinedButton.icon(
                          onPressed: locked ? null : pickFiles,
                          icon: const Icon(Icons.add),
                          label: Text(files.isEmpty ? 'Choose files' : 'Add more'),
                        ),
                        if (files.isNotEmpty) ...[
                          const SizedBox(width: 8),
                          TextButton(
                            onPressed: locked ? null : () => setState(files.clear),
                            child: const Text('Clear all'),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text('DICOM: .dcm, .dicom   Video: .avi, .mp4, .mov, .mkv',
                        style: theme.textTheme.bodySmall),
                  ],
                ),
              ),

              _Step(
                number: 2,
                title: 'Output folder',
                done: folder != null,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (folder != null)
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(10),
                        margin: const EdgeInsets.only(bottom: 10),
                        decoration: BoxDecoration(
                          color: theme.colorScheme.surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: SelectableText(folder!,
                            style: const TextStyle(fontFamily: 'monospace')),
                      ),
                    OutlinedButton.icon(
                      onPressed: locked || choosingFolder ? null : chooseFolder,
                      icon: choosingFolder
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.folder_open),
                      label: Text(choosingFolder
                          ? 'Waiting for selection...'
                          : folder == null
                              ? 'Choose folder'
                              : 'Change folder'),
                    ),
                  ],
                ),
              ),

              _Step(
                number: 3,
                title: 'Output format',
                done: true,
                child: SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'png', label: Text('PNG (lossless)')),
                    ButtonSegment(value: 'jpg', label: Text('JPG (smaller)')),
                  ],
                  selected: {format},
                  onSelectionChanged:
                      locked ? null : (s) => setState(() => format = s.first),
                ),
              ),

              const SizedBox(height: 8),
              if (state != null) _result(context),
              if (status == JobStatus.idle)
                SizedBox(
                  height: 48,
                  child: FilledButton.icon(
                    onPressed:
                        busy || files.isEmpty || folder == null ? null : start,
                    icon: busy
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white))
                        : const Icon(Icons.play_arrow),
                    label: Text(busy ? 'Uploading...' : 'Start processing'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _result(BuildContext context) {
    final theme = Theme.of(context);
    final job = state!;
    final done = (job['files_completed'] ?? 0) as num;
    final total = (job['total_files'] ?? 0) as num;

    final (color, icon, title) = switch (status) {
      JobStatus.completed => (
          theme.colorScheme.primaryContainer,
          Icons.check_circle,
          'Processing complete'
        ),
      JobStatus.failed => (
          theme.colorScheme.errorContainer,
          Icons.error,
          'Processing needs attention'
        ),
      _ => (null, Icons.sync, 'Processing...'),
    };

    return Card(
      color: color,
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(icon),
              const SizedBox(width: 8),
              Text(title, style: theme.textTheme.titleLarge),
            ]),
            const SizedBox(height: 8),
            Text(status == JobStatus.failed
                ? '${job['message'] ?? ''} ${job['error'] ?? ''}'
                : '${job['message'] ?? ''}'),
            if (status == JobStatus.running) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(value: total == 0 ? null : done / total),
              const SizedBox(height: 4),
              Text('$done of $total files', style: theme.textTheme.bodySmall),
            ],
            if (status == JobStatus.completed) ...[
              const SizedBox(height: 4),
              Text('$done of $total files processed, '
                  '${job['frames_created'] ?? 0} frames saved.'),
            ],
            if (status == JobStatus.running) ...[
              const SizedBox(height: 12),
              LinearProgressIndicator(value: total == 0 ? null : done / total),
              const SizedBox(height: 4),
              Text(
                '$done of $total files  ·  ${job['frames_created'] ?? 0} frames so far',
                style: theme.textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }

  static IconData _iconFor(String name) {
    final ext = name.split('.').last.toLowerCase();
    return (ext == 'dcm' || ext == 'dicom')
        ? Icons.medical_information_outlined
        : Icons.movie_outlined;
  }

  static String _size(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
    }
    return '${(bytes / 1024 / 1024 / 1024).toStringAsFixed(2)} GB';
  }
}

// --------------------------------------------------------------- widgets

class _Step extends StatelessWidget {
  const _Step({
    required this.number,
    required this.title,
    required this.done,
    required this.child,
  });

  final int number;
  final String title;
  final bool done;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(
              radius: 14,
              backgroundColor: done
                  ? theme.colorScheme.primary
                  : theme.colorScheme.surfaceContainerHighest,
              child: done
                  ? Icon(Icons.check, size: 16, color: theme.colorScheme.onPrimary)
                  : Text('$number', style: theme.textTheme.labelLarge),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: theme.textTheme.titleMedium),
                  const SizedBox(height: 10),
                  child,
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.message, required this.onClose});

  final String message;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    return Material(
      color: c.errorContainer,
      borderRadius: BorderRadius.circular(10),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 4, 8),
        child: Row(children: [
          Icon(Icons.warning_amber, color: c.onErrorContainer),
          const SizedBox(width: 10),
          Expanded(
              child: Text(message, style: TextStyle(color: c.onErrorContainer))),
          IconButton(onPressed: onClose, icon: const Icon(Icons.close)),
        ]),
      ),
    );
  }
}
