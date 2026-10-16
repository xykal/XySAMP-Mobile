#include "CFPSFix.h"
#include "main.h"
#include <sys/syscall.h>
#include <algorithm>
#include <unistd.h>

// Kernel mengharapkan ukuran mask sama dengan unsigned long (4 byte di 32-bit, 8 byte di 64-bit).
// Memakai uint32_t di arm64 membuat sched_setaffinity gagal diam-diam (EINVAL).
static void setThreadAffinityMask(pid_t tid, unsigned long mask)
{
	syscall(__NR_sched_setaffinity, tid, sizeof(mask), &mask);
}

// Thread yang sudah selesai dibuang dari daftar; TID bisa dipakai ulang oleh thread lain.
static bool isThreadAlive(pid_t pid, pid_t tid)
{
	return syscall(SYS_tgkill, pid, tid, 0) == 0;
}

void CFPSFix::Routine()
{
	while (true)
	{
		m_Mutex.lock();
		pid_t pid = getpid();
		m_Threads.erase(std::remove_if(m_Threads.begin(), m_Threads.end(),
			[pid](pid_t tid) { return !isThreadAlive(pid, tid); }), m_Threads.end());
		for (auto& i : m_Threads)
		{
			unsigned long mask = 0xff;

			setThreadAffinityMask(i, mask);
		}
		m_Mutex.unlock();

		std::this_thread::sleep_for(std::chrono::milliseconds(1000));
	}
}

CFPSFix::CFPSFix()
{
	std::thread(&CFPSFix::Routine, this).detach();
}

CFPSFix::~CFPSFix()
{
}

void CFPSFix::PushThread(pid_t tid)
{
	std::lock_guard<std::mutex> lock(m_Mutex);

	m_Threads.push_back(tid);
}
