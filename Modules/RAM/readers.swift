//
//  readers.swift
//  Memory
//
//  Created by Serhiy Mytrovtsiy on 12/04/2020.
//  Using Swift 5.0.
//  Running on macOS 10.15.
//
//  Copyright © 2020 Serhiy Mytrovtsiy. All rights reserved.
//

import Cocoa
import Kit
import Darwin.libproc

internal class UsageReader: Reader<RAM_Usage> {
    public var totalSize: Double = 0
    
    public override func setup() {
        var stats = host_basic_info()
        var count = UInt32(MemoryLayout<host_basic_info_data_t>.size / MemoryLayout<integer_t>.size)
        
        let kerr: kern_return_t = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                host_info(mach_host_self(), HOST_BASIC_INFO, $0, &count)
            }
        }
        
        if kerr == KERN_SUCCESS {
            self.totalSize = Double(stats.max_mem)
            return
        }
        
        self.totalSize = 0
        error("host_info(): \(String(cString: mach_error_string(kerr), encoding: String.Encoding.ascii) ?? "unknown error")", log: self.log)
    }
    
    public override func read() {
        var stats = vm_statistics64()
        var count = UInt32(MemoryLayout<vm_statistics64_data_t>.size / MemoryLayout<integer_t>.size)
        
        let result: kern_return_t = withUnsafeMutablePointer(to: &stats) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                host_statistics64(mach_host_self(), HOST_VM_INFO64, $0, &count)
            }
        }
        
        if result == KERN_SUCCESS {
            let active = Double(stats.active_count) * Double(vm_page_size)
            let speculative = Double(stats.speculative_count) * Double(vm_page_size)
            let inactive = Double(stats.inactive_count) * Double(vm_page_size)
            let wired = Double(stats.wire_count) * Double(vm_page_size)
            let compressed = Double(stats.compressor_page_count) * Double(vm_page_size)
            let purgeable = Double(stats.purgeable_count) * Double(vm_page_size)
            let external = Double(stats.external_page_count) * Double(vm_page_size)
            let swapins = Int64(stats.swapins)
            let swapouts = Int64(stats.swapouts)
            
            let used = active + inactive + speculative + wired + compressed - purgeable - external
            let free = self.totalSize - used
            
            var intSize: size_t = MemoryLayout<uint>.size
            var pressureLevel: Int = 0
            sysctlbyname("kern.memorystatus_vm_pressure_level", &pressureLevel, &intSize, nil, 0)
            
            var pressureValue: RAMPressure
            switch pressureLevel {
            case 2: pressureValue = .warning
            case 4: pressureValue = .critical
            default: pressureValue = .normal
            }
            
            var stringSize: size_t = MemoryLayout<xsw_usage>.size
            var swap: xsw_usage = xsw_usage()
            sysctlbyname("vm.swapusage", &swap, &stringSize, nil, 0)
            
            self.callback(RAM_Usage(
                total: self.totalSize,
                used: used,
                free: free,
                
                active: active,
                inactive: inactive,
                wired: wired,
                compressed: compressed,
                
                app: used - wired - compressed,
                cache: purgeable + external,
                
                swap: Swap(
                    total: Double(swap.xsu_total),
                    used: Double(swap.xsu_used),
                    free: Double(swap.xsu_avail)
                ),
                pressure: Pressure(level: pressureLevel, value: pressureValue),
                
                swapins: swapins,
                swapouts: swapouts
            ))
            return
        }
        
        error("host_statistics64(): \(String(cString: mach_error_string(result), encoding: String.Encoding.ascii) ?? "unknown error")", log: self.log)
    }
}

public class ProcessReader: Reader<[TopProcess]> {
    private let title: String = "RAM"
    
    private var numberOfProcesses: Int {
        get { Store.shared.int(key: "\(self.title)_processes", defaultValue: 8) }
    }
    
    private var combinedProcesses: Bool{
        get { Store.shared.bool(key: "\(self.title)_combinedProcesses", defaultValue: false) }
    }
    
    private typealias dynGetResponsiblePidFuncType = @convention(c) (CInt) -> CInt
    
    public override func setup() {
        self.popup = true
        self.setInterval(Store.shared.int(key: "\(self.title)_updateTopInterval", defaultValue: 1))
    }
    
    public override func read() {
        if self.numberOfProcesses == 0 {
            return
        }
        
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/top")
        if self.combinedProcesses {
            task.arguments = ["-l", "1", "-o", "mem", "-stats", "pid,command,mem"]
        } else {
            task.arguments = ["-l", "1", "-o", "mem", "-n", "\(self.numberOfProcesses)", "-stats", "pid,command,mem"]
        }
        
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        
        defer {
            outputPipe.fileHandleForReading.closeFile()
            errorPipe.fileHandleForReading.closeFile()
        }
        
        task.standardOutput = outputPipe
        task.standardError = errorPipe
        
        do {
            try task.run()
        } catch let err {
            error("top(): \(err.localizedDescription)", log: self.log)
            return
        }
        
        let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
        let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: outputData, encoding: .utf8)
        _ = String(data: errorData, encoding: .utf8)
        guard let output, !output.isEmpty else { return }
        
        var processes: [TopProcess] = []
        output.enumerateLines { (line, _) in
            if line.matches("^\\d+\\** +.* +\\d+[A-Z]*\\+?\\-? *$") {
                processes.append(ProcessReader.parseProcess(line))
            }
        }
        
        if !self.combinedProcesses {
            self.callback(processes)
            return
        }
        
        var processGroups: [String: (name: String, mainPid: Int, totalUsage: Double, procs: [TopProcess])] = [:]
        for process in processes {
            let (resolvedName, appPid) = ProcessReader.resolveAppName(pid: process.pid, defaultName: process.name)
            let groupKey = resolvedName
            
            if var existing = processGroups[groupKey] {
                existing.totalUsage += process.usage
                existing.procs.append(process)
                if NSRunningApplication(processIdentifier: pid_t(process.pid))?.icon != nil {
                    existing.mainPid = process.pid
                }
                processGroups[groupKey] = existing
            } else {
                processGroups[groupKey] = (name: resolvedName, mainPid: appPid, totalUsage: process.usage, procs: [process])
            }
        }
        
        var result: [TopProcess] = []
        for (_, group) in processGroups {
            result.append(TopProcess(
                pid: group.mainPid,
                name: group.name,
                usage: group.totalUsage
            ))
        }
        
        result.sort { $0.usage > $1.usage }
        self.callback(Array(result.prefix(self.numberOfProcesses)))
    }
    
    private static func getProcessPath(pid: Int32) -> String? {
        var pathBuffer = [CChar](repeating: 0, count: Int(MAXPATHLEN))
        let pathLength = proc_pidpath(pid, &pathBuffer, UInt32(pathBuffer.count))
        if pathLength > 0 {
            return String(cString: pathBuffer)
        }
        return nil
    }
    
    public static func resolveAppName(pid: Int, defaultName: String) -> (name: String, appPid: Int) {
        let responsiblePid = ProcessReader.getResponsiblePid(pid)
        let candidatePid = (responsiblePid > 0) ? responsiblePid : pid
        
        if let app = NSRunningApplication(processIdentifier: pid_t(candidatePid)),
           let appName = app.localizedName, !appName.isEmpty {
            return (appName, candidatePid)
        }
        
        if let app = NSRunningApplication(processIdentifier: pid_t(pid)),
           let appName = app.localizedName, !appName.isEmpty {
            return (appName, pid)
        }
        
        for p in [pid, candidatePid] {
            if let path = getProcessPath(pid: Int32(p)) {
                if let match = path.range(of: #"/([^/]+)\.app"#, options: .regularExpression) {
                    let bundle = String(path[match])
                        .replacingOccurrences(of: ".app", with: "")
                        .replacingOccurrences(of: "/", with: "")
                    if !bundle.isEmpty {
                        return (bundle, p)
                    }
                }
            }
        }
        
        let cleanName: String
        if defaultName.contains("Google Chrome") || defaultName.contains("chrome-devtools") {
            cleanName = "Google Chrome"
        } else if defaultName.contains("Dia") || defaultName.contains("ArcCore") || defaultName.contains("Browser Helper") {
            cleanName = "Dia"
        } else if defaultName.contains("Safari") || defaultName.contains("WebKit") {
            cleanName = "Safari"
        } else if defaultName.contains("Code Helper") || defaultName.contains("Visual Studio Code") {
            cleanName = "Visual Studio Code"
        } else if defaultName.contains("Cursor") {
            cleanName = "Cursor"
        } else if defaultName.contains("Slack") {
            cleanName = "Slack"
        } else if defaultName.contains("WhatsApp") {
            cleanName = "WhatsApp"
        } else if defaultName.contains("Spotify") {
            cleanName = "Spotify"
        } else if defaultName.contains("Antigravity") {
            cleanName = "Antigravity"
        } else if defaultName.contains("com.apple.Virtua") && defaultName.contains("Docker") {
            cleanName = "Docker"
        } else {
            cleanName = defaultName
        }
        
        return (cleanName, candidatePid)
    }
    
    private static let dynGetResponsiblePidFunc: UnsafeMutableRawPointer? = {
        let result = dlsym(UnsafeMutableRawPointer(bitPattern: -1), "responsibility_get_pid_responsible_for_pid")
        if result == nil {
            error("Error loading responsibility_get_pid_responsible_for_pid")
        }
        return result
    }()
    
    static func getResponsiblePid(_ childPid: Int) -> Int {
        guard ProcessReader.dynGetResponsiblePidFunc != nil else {
            return childPid
        }
        let responsiblePid = unsafeBitCast(ProcessReader.dynGetResponsiblePidFunc, to: dynGetResponsiblePidFuncType.self)(CInt(childPid))
        guard responsiblePid != -1 else {
            return childPid
        }
        return Int(responsiblePid)
    }
    
    static public func parseProcess(_ raw: String) -> TopProcess {
        var str = raw.trimmingCharacters(in: .whitespaces)
        let pidString = str.find(pattern: "^\\d+")
        
        if let range = str.range(of: pidString) {
            str = str.replacingCharacters(in: range, with: "")
        }
        
        var arr = str.split(separator: " ")
        if arr.first == "*" {
            arr.removeFirst()
        }
        
        var usageString = str.suffix(6)
        if let lastElement = arr.last {
            usageString = lastElement
            arr.removeLast()
        }
        
        var command = arr.joined(separator: " ")
            .replacingOccurrences(of: pidString, with: "")
            .trimmingCharacters(in: .whitespaces)
        
        if let regex = try? NSRegularExpression(pattern: " (\\+|\\-)*$", options: .caseInsensitive) {
            command = regex.stringByReplacingMatches(in: command, options: [], range: NSRange(location: 0, length: command.count), withTemplate: "")
        }
        
        let pid = Int(pidString.filter("01234567890.".contains)) ?? 0
        var usage = Double(usageString.filter("01234567890.".contains)) ?? 0
        if usageString.last == "G" {
            usage *= 1024 // apply gigabyte multiplier
        } else if usageString.last == "K" {
            usage /= 1024 // apply kilobyte divider
        } else if usageString.last == "M" && usageString.count == 5 {
            usage /= 1024
            usage *= 1000
        }
        
        let (name, resolvedPid) = ProcessReader.resolveAppName(pid: pid, defaultName: command)
        
        return TopProcess(pid: resolvedPid, name: name, usage: usage * Double(1000 * 1000))
    }
}
