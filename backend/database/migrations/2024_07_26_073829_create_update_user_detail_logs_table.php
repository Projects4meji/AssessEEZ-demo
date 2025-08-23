<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('update_user_detail_logs', function (Blueprint $table) {
            $table->id();
            $table->integer('user_id')->nullable();
            $table->longText('message')->nullable();
            $table->string('attachment')->nullable();
            $table->integer('pre_assessor_id')->nullable();
            $table->integer('new_assessor_id')->nullable();
            $table->integer('pre_iqa_id')->nullable();
            $table->integer('new_iqa_id')->nullable();
            $table->integer('pre_qualification_id')->nullable();
            $table->integer('new_qualification_id')->nullable();
            $table->integer('created_by')->nullable();
            $table->integer('updated_by')->nullable();
            $table->timestamp('created_at')->useCurrent();
            $table->timestamp('updated_at')->useCurrent();
            $table->softDeletes();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('update_user_detail_logs');
    }
};
