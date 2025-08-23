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
        Schema::table('user_qualifications', function (Blueprint $table) {
            $table->string('ref_number')->nullable();
            $table->string('contact')->nullable();
            $table->date('date_of_birth')->nullable();
            $table->string('cohort_batch_no')->nullable();
            $table->date('date_of_registration')->nullable();
            $table->float('sampling_ratio')->nullable();
            $table->integer('view_only_id')->nullable();
            $table->string('learner_number')->nullable();
            $table->longText('location')->nullable();
            $table->string('country')->nullable();
            $table->string('city')->nullable();
            $table->string('lat')->nullable();
            $table->string('lon')->nullable();
            $table->date('expiry_date')->nullable();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('user_qualifications', function (Blueprint $table) {
            //
        });
    }
};
